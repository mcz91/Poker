"""Maszyna licytacji heads-up: legalność akcji, przebieg ulic, rozliczenie puli."""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from poker.dealing import DealtHand, deal_hand, shuffled_deck
from poker.evaluation import evaluate_best
from poker.events import (
    ActionTaken,
    ActionType,
    BlindPosted,
    BlindType,
    CardsRevealed,
    DeckSeeded,
    FlopDealt,
    HandConfig,
    HandEnded,
    HandEvent,
    HandStarted,
    HoleCardsDealt,
    PotAwarded,
    RiverDealt,
    TurnDealt,
    UncalledBetReturned,
)
from poker.history import HandHistory
from poker.projection import TableState, project


@dataclass(frozen=True, slots=True)
class ActionBounds:
    minimum: int
    maximum: int


@dataclass(frozen=True, slots=True)
class LegalActions:
    seat: int
    fold_allowed: bool
    check_allowed: bool
    call_amount: int | None
    bet_range: ActionBounds | None
    raise_range: ActionBounds | None


def split_pot(
    pot: int, winners: Sequence[int], button: int, seat_count: int
) -> tuple[tuple[int, int], ...]:
    """Dzieli pulę; niepodzielna reszta trafia kolejno od miejsca po lewej buttona."""
    if pot < 0:
        raise ValueError(f"pula nie może być ujemna: {pot}")
    if not winners:
        raise ValueError("podział puli wymaga co najmniej jednego zwycięzcy")
    ordered = sorted(winners, key=lambda seat: (seat - button - 1) % seat_count)
    base, rest = divmod(pot, len(ordered))
    return tuple(
        (seat, base + (1 if index < rest else 0)) for index, seat in enumerate(ordered)
    )


@dataclass(frozen=True, slots=True)
class _BettingView:
    stacks: tuple[int, ...]
    pot: int
    committed_street: tuple[int, ...]
    committed_total: tuple[int, ...]
    current_bet: int
    last_raise: int
    reopen: bool
    acted: frozenset[int]
    folded: frozenset[int]
    board_len: int
    street_aggressor: int | None
    finished: bool


def _view(events: Sequence[HandEvent], config: HandConfig) -> _BettingView:
    seats = len(config.stacks)
    stacks = list(config.stacks)
    pot = 0
    committed_street = [0] * seats
    committed_total = [0] * seats
    current_bet = 0
    last_raise = config.big_blind
    reopen = True
    acted: set[int] = set()
    folded: set[int] = set()
    board_len = 0
    aggressor: int | None = None
    finished = False

    def nowa_ulica(length: int) -> None:
        nonlocal board_len, current_bet, last_raise, reopen, acted, aggressor
        board_len = length
        committed_street[:] = [0] * seats
        current_bet = 0
        last_raise = config.big_blind
        reopen = True
        acted = set()
        aggressor = None

    for event in events[1:]:
        match event:
            case BlindPosted(seat=seat, amount=amount):
                stacks[seat] -= amount
                pot += amount
                committed_street[seat] += amount
                committed_total[seat] += amount
                current_bet = max(current_bet, committed_street[seat])
            case HoleCardsDealt() | DeckSeeded():
                pass
            case FlopDealt():
                nowa_ulica(3)
            case TurnDealt():
                nowa_ulica(4)
            case RiverDealt():
                nowa_ulica(5)
            case ActionTaken(seat=seat, action=action, amount=amount):
                acted.add(seat)
                if action is ActionType.FOLD:
                    folded.add(seat)
                elif action is not ActionType.CHECK:
                    stacks[seat] -= amount
                    pot += amount
                    committed_street[seat] += amount
                    committed_total[seat] += amount
                    if action is not ActionType.CALL:
                        raise_size = committed_street[seat] - current_bet
                        reopen = raise_size >= last_raise
                        if reopen:
                            last_raise = raise_size
                        current_bet = committed_street[seat]
                        acted = {seat}
                        aggressor = seat
            case PotAwarded(seat=seat, amount=amount) | UncalledBetReturned(
                seat=seat, amount=amount
            ):
                stacks[seat] += amount
                pot -= amount
                finished = True
            case CardsRevealed() | HandEnded():
                finished = True
            case HandStarted():
                raise ValueError("start rozdania może wystąpić wyłącznie jako pierwsze zdarzenie")

    return _BettingView(
        stacks=tuple(stacks),
        pot=pot,
        committed_street=tuple(committed_street),
        committed_total=tuple(committed_total),
        current_bet=current_bet,
        last_raise=last_raise,
        reopen=reopen,
        acted=frozenset(acted),
        folded=frozenset(folded),
        board_len=board_len,
        street_aggressor=aggressor,
        finished=finished,
    )


class HeadsUpHand:
    """Rozdanie heads-up: przebieg istnieje wyłącznie jako zdarzenia w historii."""

    def __init__(self, config: HandConfig, seed: int) -> None:
        if len(config.stacks) != 2:
            raise ValueError(
                "maszyna licytacji obsługuje dokładnie 2 miejsca (heads-up); "
                "multiway wymaga decyzji architekta"
            )
        if any(stack == 0 for stack in config.stacks):
            raise ValueError("każde miejsce musi wnieść żetony do rozdania")
        self._config = config
        self._button = config.button
        self._dealt: DealtHand = deal_hand(shuffled_deck(random.Random(seed)), seat_count=2)
        self._history = HandHistory()
        self._history.append(HandStarted(config=config))
        self._history.append(DeckSeeded(seed=seed))
        small_seat, big_seat = self._button, 1 - self._button
        self._history.append(
            BlindPosted(
                seat=small_seat,
                blind=BlindType.SMALL,
                amount=min(config.small_blind, config.stacks[small_seat]),
            )
        )
        self._history.append(
            BlindPosted(
                seat=big_seat,
                blind=BlindType.BIG,
                amount=min(config.big_blind, config.stacks[big_seat]),
            )
        )
        for hole in self._dealt.hole_cards:
            self._history.append(hole)
        self._advance()

    def events(self) -> tuple[HandEvent, ...]:
        return self._history.events()

    def state(self) -> TableState:
        return project(self.events())

    def to_act(self) -> int | None:
        return self._to_act(_view(self.events(), self._config))

    def legal_actions(self) -> LegalActions | None:
        view = _view(self.events(), self._config)
        seat = self._to_act(view)
        if seat is None:
            return None
        opponent = 1 - seat
        to_call = view.current_bet - view.committed_street[seat]
        stack = view.stacks[seat]
        opponent_all_in = view.stacks[opponent] == 0
        bet_range = None
        if view.current_bet == 0 and not opponent_all_in:
            bet_range = ActionBounds(minimum=min(self._config.big_blind, stack), maximum=stack)
        raise_range = None
        if view.current_bet > 0 and not opponent_all_in and view.reopen and stack > to_call:
            full_minimum = to_call + view.last_raise
            if stack <= full_minimum:
                raise_range = ActionBounds(minimum=stack, maximum=stack)
            else:
                raise_range = ActionBounds(minimum=full_minimum, maximum=stack)
        return LegalActions(
            seat=seat,
            fold_allowed=True,
            check_allowed=to_call == 0,
            call_amount=min(to_call, stack) if to_call > 0 else None,
            bet_range=bet_range,
            raise_range=raise_range,
        )

    def act(self, seat: int, action: ActionType, amount: int = 0) -> None:
        legal = self.legal_actions()
        if legal is None or legal.seat != seat:
            raise ValueError(f"miejsce {seat} nie jest na ruchu")
        match action:
            case ActionType.FOLD:
                self._require_no_amount(action, amount)
                self._history.append(ActionTaken(seat=seat, action=action, amount=0))
                self._settle_fold(folded=seat)
                return
            case ActionType.CHECK:
                if not legal.check_allowed:
                    raise ValueError("check niedostępny wobec zakładu do wyrównania")
                self._require_no_amount(action, amount)
                self._history.append(ActionTaken(seat=seat, action=action, amount=0))
            case ActionType.CALL:
                if legal.call_amount is None:
                    raise ValueError("brak zakładu do sprawdzenia")
                self._require_no_amount(action, amount)
                self._history.append(
                    ActionTaken(seat=seat, action=action, amount=legal.call_amount)
                )
            case ActionType.BET:
                if legal.bet_range is None:
                    raise ValueError("zakład niedostępny w tym stanie licytacji")
                self._require_in_bounds(legal.bet_range, amount, "zakładu")
                self._history.append(ActionTaken(seat=seat, action=action, amount=amount))
            case ActionType.RAISE:
                if legal.raise_range is None:
                    raise ValueError("podbicie niedostępne w tym stanie licytacji")
                self._require_in_bounds(legal.raise_range, amount, "podbicia")
                self._history.append(ActionTaken(seat=seat, action=action, amount=amount))
        self._advance()

    def _require_no_amount(self, action: ActionType, amount: int) -> None:
        if amount != 0:
            raise ValueError(f"akcja {action.value} nie przyjmuje kwoty — wyznacza ją silnik")

    def _require_in_bounds(self, bounds: ActionBounds, amount: int, label: str) -> None:
        if not bounds.minimum <= amount <= bounds.maximum:
            raise ValueError(
                f"kwota {label} {amount} poza granicami "
                f"[{bounds.minimum}, {bounds.maximum}]"
            )

    def _street_order(self, board_len: int) -> tuple[int, int]:
        if board_len == 0:
            return (self._button, 1 - self._button)
        return (1 - self._button, self._button)

    def _to_act(self, view: _BettingView) -> int | None:
        if view.finished or view.folded:
            return None
        for seat in (0, 1):
            to_call = view.current_bet - view.committed_street[seat]
            if to_call > 0:
                return seat if view.stacks[seat] > 0 else None
        if view.stacks[0] == 0 or view.stacks[1] == 0:
            return None
        for seat in self._street_order(view.board_len):
            if seat not in view.acted:
                return seat
        return None

    def _advance(self) -> None:
        view = _view(self.events(), self._config)
        if view.finished or view.folded or self._to_act(view) is not None:
            return
        remaining: tuple[FlopDealt | TurnDealt | RiverDealt, ...] = {
            0: (self._dealt.flop, self._dealt.turn, self._dealt.river),
            3: (self._dealt.turn, self._dealt.river),
            4: (self._dealt.river,),
            5: (),
        }[view.board_len]
        betting_possible = view.stacks[0] > 0 and view.stacks[1] > 0
        if not betting_possible:
            for board_event in remaining:
                self._history.append(board_event)
            self._showdown()
        elif remaining:
            self._history.append(remaining[0])
        else:
            self._showdown()

    def _settle_fold(self, folded: int) -> None:
        view = _view(self.events(), self._config)
        self._history.append(PotAwarded(seat=1 - folded, amount=view.pot))
        self._history.append(HandEnded())

    def _showdown(self) -> None:
        view = _view(self.events(), self._config)
        overpay = view.committed_total[0] - view.committed_total[1]
        if overpay != 0:
            overpayer = 0 if overpay > 0 else 1
            self._history.append(UncalledBetReturned(seat=overpayer, amount=abs(overpay)))
        first = (
            view.street_aggressor if view.street_aggressor is not None else 1 - self._button
        )
        hole = {event.seat: event.cards for event in self._dealt.hole_cards}
        for seat in (first, 1 - first):
            self._history.append(CardsRevealed(seat=seat, cards=hole[seat]))
        board = (*self._dealt.flop.cards, self._dealt.turn.card, self._dealt.river.card)
        values = {seat: evaluate_best(hole[seat] + board) for seat in (0, 1)}
        best = max(values.values())
        winners = [seat for seat in (0, 1) if values[seat] == best]
        pot = view.pot - abs(overpay)
        for seat, amount in split_pot(pot, winners, self._button, seat_count=2):
            if amount > 0:
                self._history.append(PotAwarded(seat=seat, amount=amount))
        self._history.append(HandEnded())
