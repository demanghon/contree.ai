use coinche_engine::data_gen::bidding::{generate_hand_batch, solve_hand_batch};
use std::time::Instant;

fn main() {
    let dataset_size = 500;
    let pimc_iterations = 20;

    println!("========================================");
    println!(" CAPOT BENCHMARK (Full Depth PIMC)");
    println!("========================================");
    println!("Dataset Size: {} hands", dataset_size);
    println!("PIMC Iterations: {}", pimc_iterations);
    println!("Solver Depth: 32 (Forced in bidding.rs)");
    println!("Transposition Table: 64MB");
    println!("----------------------------------------");

    // 1. Generation
    println!("Generatings hands...");
    let (hands, strategies) = generate_hand_batch(dataset_size);

    // Count theoretical strategies
    let mut capot_strat_count = 0;
    for &s in &strategies {
        if s == 1 {
            // ForceCapot
            capot_strat_count += 1;
        }
    }
    println!(
        "Generated Hands with 'ForceCapot' strategy: {}",
        capot_strat_count
    );

    // 2. Solving
    println!("Solving... (This may take a while per hand)");
    let start_time = Instant::now();
    let tt_log2 = 22; // 64MB
    let scores_batch = solve_hand_batch(hands, pimc_iterations, Some(tt_log2));
    let total_duration = start_time.elapsed();

    // 3. Analysis
    let mut capot_found_count = 0;
    let mut max_score_found = 0.0;
    let mut total_score_acc = 0.0;

    for scores in &scores_batch {
        // scores is Vec<f32> of size 4 (one per trump)
        // We look broadly: did we find ANY capot in this deal?
        for &s in scores {
            if s > max_score_found {
                max_score_found = s;
            }
            if s >= 250.0 {
                capot_found_count += 1;
                // Count one capot per deal? Or total capot contracts found?
                // Usually we care if the hand SUPPORTS a capot.
            }
            total_score_acc += s;
        }
    }

    // De-dup capot counting (per deal)
    let mut deals_with_capot = 0;
    for scores in &scores_batch {
        let mut has_capot = false;
        for &s in scores {
            if s >= 250.0 {
                has_capot = true;
            }
        }
        if has_capot {
            deals_with_capot += 1;
        }
    }

    let avg_time_per_hand = total_duration.as_secs_f64() / dataset_size as f64;
    let hands_per_sec = 1.0 / avg_time_per_hand;

    println!("----------------------------------------");
    println!(" RESULTS");
    println!("----------------------------------------");
    println!("Total Time       : {:.2?}", total_duration);
    println!("Avg Time/Hand    : {:.4} s", avg_time_per_hand);
    println!("Throughput       : {:.2} hands/s", hands_per_sec);
    println!("----------------------------------------");
    println!("Max Score Found  : {:.1}", max_score_found);
    println!("Deals w/ Capot   : {} / {}", deals_with_capot, dataset_size);
    println!("Theoretical Capot: {} (Strategy-based)", capot_strat_count);
    println!("----------------------------------------");

    if deals_with_capot > 0 {
        println!("✅ SUCCESS: Capot scores (250+) detected!");
    } else {
        println!("❌ FAILURE: No Capot scores detected. Solver depth might still be limited.");
    }
}
