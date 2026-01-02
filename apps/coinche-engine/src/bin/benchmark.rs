use coinche_engine::data_gen::bidding::generate_hand_batch;
use coinche_engine::data_gen::bidding::solve_hand_batch;
use std::time::Instant;

fn main() {
    let batch_size = 100;
    println!("Generating {} hands...", batch_size);
    let (hands, _) = generate_hand_batch(batch_size);

    println!("Solving {} hands...", batch_size);
    let start = Instant::now();
    let _scores = solve_hand_batch(hands, 1);
    let duration = start.elapsed();

    println!("Solved {} hands in {:.4?}", batch_size, duration);
    println!(
        "Speed: {:.2} hands/second",
        batch_size as f64 / duration.as_secs_f64()
    );
}
