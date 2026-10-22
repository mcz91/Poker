// SPDX-License-Identifier: AGPL-3.0-or-later
// hupf: HU postflop driver around b-inary postflop-solver (AGPL-3.0; upstream at a pinned commit
// plus min_bet.patch, fetched into vendor/ by build.sh).
//
// Usage:
//   hupf solve <job.txt>      one job, JSON to the path given by `out` (or stdout)
//   hupf serve                jobs on stdin, each terminated by a line `END`; one JSON line per job
//
// Job format: one `key value` per line. Ranges are 1326 whitespace-separated weights in [0, 1],
// indexed like b-inary (`card = 4*rank + suit`, rank 0 = deuce, suit c,d,h,s; pair index
// c1*(101-c1)/2 + c2 - 1 with c1 < c2). Player 0 = OOP (BB in HU), player 1 = IP (SB/button).
// Amounts are integer chips; the Python side uses 1 bb = 100 chips.
use postflop_solver::*;
use std::collections::HashMap;
use std::fmt::Write as _;
use std::io::{BufRead, Write};
use std::time::Instant;

struct Job {
    kv: HashMap<String, String>,
}

impl Job {
    fn get(&self, k: &str) -> Option<&str> {
        self.kv.get(k).map(|s| s.as_str())
    }
    fn s(&self, k: &str, d: &str) -> String {
        self.get(k).unwrap_or(d).to_string()
    }
    fn f(&self, k: &str, d: f64) -> f64 {
        self.get(k).map(|v| v.parse().expect(k)).unwrap_or(d)
    }
    fn i(&self, k: &str, d: i64) -> i64 {
        self.get(k).map(|v| v.parse().expect(k)).unwrap_or(d)
    }
}

fn parse_job(lines: &[String]) -> Job {
    let mut kv = HashMap::new();
    for l in lines {
        let l = l.trim();
        if l.is_empty() || l.starts_with('#') {
            continue;
        }
        let (k, v) = match l.split_once(char::is_whitespace) {
            Some((k, v)) => (k, v.trim()),
            None => (l, ""),
        };
        kv.insert(k.to_string(), v.to_string());
    }
    Job { kv }
}

fn pair_index(c1: u8, c2: u8) -> usize {
    let (a, b) = if c1 < c2 { (c1, c2) } else { (c2, c1) };
    a as usize * (101 - a as usize) / 2 + b as usize - 1
}

fn parse_range(s: &str) -> Result<Range, String> {
    let v: Vec<f32> = s
        .split_whitespace()
        .map(|x| x.parse::<f32>().map_err(|e| e.to_string()))
        .collect::<Result<_, _>>()?;
    Range::from_raw_data(&v)
}

fn parse_board(s: &str) -> Result<Vec<u8>, String> {
    let chars: Vec<char> = s.chars().filter(|c| !c.is_whitespace()).collect();
    if chars.len() % 2 != 0 {
        return Err(format!("bad board {s}"));
    }
    chars
        .chunks(2)
        .map(|c| card_from_str(&c.iter().collect::<String>()))
        .collect()
}

fn fmt_arr(out: &mut String, v: &[f32]) {
    out.push('[');
    for (i, x) in v.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        if *x == 0.0 {
            out.push('0');
        } else {
            let _ = write!(out, "{:.6}", x);
        }
    }
    out.push(']');
}

fn to1326(game: &PostFlopGame, player: usize, v: &[f32]) -> Vec<f32> {
    let mut r = vec![0.0f32; 1326];
    for (h, &(c1, c2)) in game.private_cards(player).iter().enumerate() {
        r[pair_index(c1, c2)] = v[h];
    }
    r
}

fn bet_opts(job: &Job, street: &str, player: &str, dbet: &str, draise: &str) -> Result<BetSizeOptions, String> {
    let b = job
        .get(&format!("{player}_{street}_bet"))
        .or(job.get(&format!("{street}_bet")))
        .unwrap_or(dbet)
        .to_string();
    let r = job
        .get(&format!("{player}_{street}_raise"))
        .or(job.get(&format!("{street}_raise")))
        .unwrap_or(draise)
        .to_string();
    BetSizeOptions::try_from((b.as_str(), r.as_str()))
}

fn aggregate(game: &PostFlopGame) -> (Vec<String>, Vec<f32>) {
    let pl = game.current_player();
    let acts = game.available_actions();
    let st = game.strategy();
    let w = game.normalized_weights(pl);
    let n = w.len();
    let tot: f32 = w.iter().sum();
    let mut freqs = Vec::new();
    for i in 0..acts.len() {
        let m: f32 = (0..n).map(|h| st[i * n + h] * w[h]).sum::<f32>();
        freqs.push(if tot > 0.0 { m / tot } else { 0.0 });
    }
    (acts.iter().map(|a| format!("{:?}", a)).collect(), freqs)
}

// Depth-first export of decision nodes on the current street, up to `depth` actions from root.
fn export_nodes(game: &mut PostFlopGame, depth: usize, path: &mut Vec<usize>, out: &mut String, first: &mut bool, with_combos: bool) {
    if game.is_terminal_node() || game.is_chance_node() {
        return;
    }
    game.cache_normalized_weights();
    let pl = game.current_player();
    let (names, freqs) = aggregate(game);
    if !*first {
        out.push(',');
    }
    *first = false;
    let p: Vec<String> = path.iter().map(|x| x.to_string()).collect();
    let _ = write!(out, "{{\"path\":\"{}\",\"player\":{},\"actions\":[", p.join(","), pl);
    for (i, a) in names.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        let _ = write!(out, "\"{}\"", a);
    }
    out.push_str("],\"freq\":");
    fmt_arr(out, &freqs);
    let tb = game.total_bet_amount();
    let _ = write!(out, ",\"bets\":[{},{}]", tb[0], tb[1]);
    if with_combos {
        let st = game.strategy();
        let n = game.num_private_hands(pl);
        out.push_str(",\"strategy\":[");
        for a in 0..names.len() {
            if a > 0 {
                out.push(',');
            }
            let row = to1326(game, pl, &st[a * n..(a + 1) * n]);
            fmt_arr(out, &row);
        }
        out.push(']');
        let evd = game.expected_values_detail(pl);
        out.push_str(",\"action_ev\":[");
        for a in 0..names.len() {
            if a > 0 {
                out.push(',');
            }
            let row = to1326(game, pl, &evd[a * n..(a + 1) * n]);
            fmt_arr(out, &row);
        }
        out.push(']');
    }
    out.push('}');
    if path.len() < depth {
        let na = names.len();
        for a in 0..na {
            let hist: Vec<usize> = game.history().to_vec();
            game.play(a);
            path.push(a);
            export_nodes(game, depth, path, out, first, with_combos);
            path.pop();
            game.apply_history(&hist);
        }
    }
}

fn run_job(job: &Job) -> Result<String, String> {
    let board = parse_board(&job.s("board", ""))?;
    if board.len() < 3 || board.len() > 5 {
        return Err("board must have 3-5 cards".into());
    }
    let pot = job.i("pot", 200) as i32;
    let stack = job.i("stack", 1400) as i32;
    let min_bet = job.i("min_bet", 100) as i32;
    MIN_BET.store(min_bet, std::sync::atomic::Ordering::Relaxed);
    let range_oop = parse_range(job.get("range_oop").ok_or("range_oop missing")?)?;
    let range_ip = parse_range(job.get("range_ip").ok_or("range_ip missing")?)?;
    let card_config = CardConfig {
        range: [range_oop, range_ip],
        flop: [board[0], board[1], board[2]],
        turn: if board.len() >= 4 { board[3] } else { NOT_DEALT },
        river: if board.len() >= 5 { board[4] } else { NOT_DEALT },
    };
    let initial_state = match board.len() {
        3 => BoardState::Flop,
        4 => BoardState::Turn,
        _ => BoardState::River,
    };
    let mut sizes = Vec::new();
    for street in ["flop", "turn", "river"] {
        let o = bet_opts(job, street, "oop", "50%, a", "a")?;
        let i = bet_opts(job, street, "ip", "50%, a", "a")?;
        sizes.push([o, i]);
    }
    let turn_donk = job.get("turn_donk").map(|s| DonkSizeOptions::try_from(s)).transpose()?;
    let river_donk = job.get("river_donk").map(|s| DonkSizeOptions::try_from(s)).transpose()?;
    let tree_config = TreeConfig {
        initial_state,
        starting_pot: pot,
        effective_stack: stack,
        rake_rate: 0.0,
        rake_cap: 0.0,
        flop_bet_sizes: sizes[0].clone(),
        turn_bet_sizes: sizes[1].clone(),
        river_bet_sizes: sizes[2].clone(),
        turn_donk_sizes: turn_donk,
        river_donk_sizes: river_donk,
        add_allin_threshold: job.f("add_allin_threshold", 1.5),
        force_allin_threshold: job.f("force_allin_threshold", 0.15),
        merging_threshold: job.f("merging_threshold", 0.1),
    };
    let t0 = Instant::now();
    let action_tree = ActionTree::new(tree_config)?;
    let mut game = PostFlopGame::with_config(card_config, action_tree)?;
    let compress = job.i("compress", 0) != 0;
    let (mem_u, mem_c) = game.memory_usage();
    let mem = if compress { mem_c } else { mem_u };
    let max_mem = (job.f("max_mem_gb", 6.0) * 1073741824.0) as u64;
    if job.i("dry", 0) != 0 {
        return Ok(format!(
            "{{\"ok\":true,\"dry\":true,\"mem_bytes\":{},\"mem_compressed_bytes\":{},\"build_s\":{:.4}}}",
            mem_u,
            mem_c,
            t0.elapsed().as_secs_f64()
        ));
    }
    if mem > max_mem {
        return Err(format!("memory {:.2} GB exceeds max_mem_gb", mem as f64 / 1073741824.0));
    }
    game.allocate_memory(compress);
    let build_s = t0.elapsed().as_secs_f64();

    let target = pot as f32 * job.f("target_pct", 0.5) as f32 / 100.0;
    let max_iter = job.i("max_iter", 1000) as u32;
    let check_every = job.i("check_every", 10).max(1) as u32;
    let progress = job.i("progress", 0) != 0;
    let t1 = Instant::now();
    let mut expl = compute_exploitability(&game);
    let mut iters = 0u32;
    while iters < max_iter && expl > target {
        solve_step(&game, iters);
        iters += 1;
        if iters % check_every == 0 || iters == max_iter {
            expl = compute_exploitability(&game);
            if progress {
                eprintln!("PROGRESS iter={} expl_pct={:.4} t={:.2}", iters, 100.0 * expl / pot as f32, t1.elapsed().as_secs_f64());
            }
        }
    }
    finalize(&mut game);
    let solve_s = t1.elapsed().as_secs_f64();

    let t2 = Instant::now();
    game.back_to_root();
    game.cache_normalized_weights();
    let mut out = String::with_capacity(1 << 20);
    let _ = write!(
        out,
        "{{\"ok\":true,\"board\":\"{}\",\"pot\":{},\"stack\":{},\"min_bet\":{},\"mem_bytes\":{},\"compress\":{},\"threads\":{},\"build_s\":{:.4},\"solve_s\":{:.4},\"iters\":{},\"expl\":{:.5},\"expl_pct\":{:.4}",
        job.s("board", ""),
        pot,
        stack,
        min_bet,
        mem,
        compress,
        std::env::var("RAYON_NUM_THREADS").unwrap_or_default().parse::<usize>().unwrap_or(0),
        build_s,
        solve_s,
        iters,
        expl,
        100.0 * expl / pot as f32
    );
    if let Some(tag) = job.get("tag") {
        let _ = write!(out, ",\"tag\":\"{}\"", tag);
    }
    let want_ev = job.i("want_ev", 1) != 0;
    if want_ev {
        out.push_str(",\"players\":[");
        let mut avg = [0.0f32; 2];
        let mut eqavg = [0.0f32; 2];
        for p in 0..2 {
            if p > 0 {
                out.push(',');
            }
            let w = to1326(&game, p, game.weights(p));
            let nw_raw = game.normalized_weights(p).to_vec();
            let nw = to1326(&game, p, &nw_raw);
            let eq_raw = game.equity(p);
            let ev_raw = game.expected_values(p);
            avg[p] = compute_average(&ev_raw, &nw_raw);
            eqavg[p] = compute_average(&eq_raw, &nw_raw);
            let eq = to1326(&game, p, &eq_raw);
            let ev = to1326(&game, p, &ev_raw);
            out.push_str("{\"weight\":");
            fmt_arr(&mut out, &w);
            out.push_str(",\"nw\":");
            fmt_arr(&mut out, &nw);
            out.push_str(",\"eq\":");
            fmt_arr(&mut out, &eq);
            out.push_str(",\"ev\":");
            fmt_arr(&mut out, &ev);
            out.push('}');
        }
        let _ = write!(out, "],\"ev_avg\":[{:.5},{:.5}],\"eq_avg\":[{:.5},{:.5}]", avg[0], avg[1], eqavg[0], eqavg[1]);
    }
    let depth = job.i("node_depth", 1) as usize;
    let with_combos = job.i("node_combos", 1) != 0;
    out.push_str(",\"nodes\":[");
    let mut first = true;
    let mut path = Vec::new();
    export_nodes(&mut game, depth, &mut path, &mut out, &mut first, with_combos);
    out.push(']');

    // Ranges/pot at a later node (e.g. turn after flop check-check), for re-solving the next street.
    if let Some(spec) = job.get("export") {
        out.push_str(",\"export\":[");
        for (k, p) in spec.split(';').filter(|s| !s.trim().is_empty()).enumerate() {
            game.back_to_root();
            let mut ok = true;
            for tok in p.split(',').map(str::trim).filter(|s| !s.is_empty()) {
                if game.is_terminal_node() {
                    ok = false;
                    break;
                }
                if let Ok(a) = tok.parse::<usize>() {
                    if game.is_chance_node() || a >= game.available_actions().len() {
                        ok = false;
                        break;
                    }
                    game.play(a);
                } else {
                    let c = card_from_str(tok)?;
                    if !game.is_chance_node() || (game.possible_cards() >> c) & 1 == 0 {
                        ok = false;
                        break;
                    }
                    game.play(c as usize);
                }
            }
            if k > 0 {
                out.push(',');
            }
            if !ok {
                let _ = write!(out, "{{\"path\":\"{}\",\"ok\":false}}", p);
                continue;
            }
            let tb = game.total_bet_amount();
            let b: Vec<String> = game.current_board().iter().map(|&c| card_to_string(c).unwrap()).collect();
            let _ = write!(
                out,
                "{{\"path\":\"{}\",\"ok\":true,\"board\":\"{}\",\"pot\":{},\"stack\":{},\"range_oop\":",
                p,
                b.join(""),
                pot + tb[0] + tb[1],
                stack - tb[0].max(tb[1])
            );
            let r0 = to1326(&game, 0, game.weights(0));
            fmt_arr(&mut out, &r0);
            out.push_str(",\"range_ip\":");
            let r1 = to1326(&game, 1, game.weights(1));
            fmt_arr(&mut out, &r1);
            out.push('}');
        }
        out.push(']');
    }
    let _ = write!(out, ",\"export_s\":{:.4}}}", t2.elapsed().as_secs_f64());
    Ok(out)
}

fn err_json(e: &str) -> String {
    format!("{{\"ok\":false,\"error\":\"{}\"}}", e.replace('"', "'"))
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(|s| s.as_str()) {
        Some("solve") => {
            let text = std::fs::read_to_string(&args[2]).expect("job file");
            let lines: Vec<String> = text.lines().map(|s| s.to_string()).collect();
            let job = parse_job(&lines);
            let res = run_job(&job).unwrap_or_else(|e| err_json(&e));
            match job.get("out") {
                Some(p) if p != "-" => std::fs::write(p, res).expect("write out"),
                _ => println!("{res}"),
            }
        }
        Some("serve") => {
            let stdin = std::io::stdin();
            let mut buf: Vec<String> = Vec::new();
            let stdout = std::io::stdout();
            for line in stdin.lock().lines() {
                let line = line.expect("stdin");
                let t = line.trim();
                if t == "QUIT" {
                    break;
                }
                if t == "END" {
                    let job = parse_job(&buf);
                    let t0 = Instant::now();
                    let mut res = run_job(&job).unwrap_or_else(|e| err_json(&e));
                    res.pop();
                    let _ = write!(res, ",\"wall_s\":{:.4}}}", t0.elapsed().as_secs_f64());
                    let mut lock = stdout.lock();
                    writeln!(lock, "{res}").unwrap();
                    lock.flush().unwrap();
                    buf.clear();
                } else {
                    buf.push(line);
                }
            }
        }
        _ => {
            eprintln!("usage: hupf solve <job.txt> | hupf serve");
            std::process::exit(2);
        }
    }
}
