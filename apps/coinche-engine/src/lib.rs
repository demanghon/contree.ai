mod data_gen;
mod game;
mod solver;

use data_gen::{
    generate_hand_batch, solve_hand_batch, write_bidding_parquet, write_gameplay_parquet,
};
use game::GameState;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use solver::solve;

#[pyfunction]
fn solve_game(state: &GameState) -> PyResult<(i16, u8)> {
    let (score, best_move) = solve(state, false);
    Ok((score, best_move))
}

#[pyfunction]
fn generate_bidding_hands(num_samples: usize) -> PyResult<(Vec<u32>, Vec<u8>)> {
    let (hands, strategies) = generate_hand_batch(num_samples);
    Ok((hands, strategies))
}

#[pyfunction]
fn solve_bidding_batch(hands: Vec<u32>) -> PyResult<Vec<Vec<i16>>> {
    let scores = solve_hand_batch(hands);
    Ok(scores)
}

#[pyfunction]
fn generate_bidding_data(path: String, num_samples: usize) -> PyResult<()> {
    // This function is now legacy/wrapper but we can keep it for now or deprecate.
    // However, since we changed generate_bidding_batch signature in bidding.rs,
    // the original implementation in bidding.rs was DELETED/REPLACED.
    // So we can't call generate_bidding_batch anymore.
    // We should either remove this function or reimplement it using the new pieces.
    // For simplicity, I'll remove it or make it error out, but better to just remove it
    // if I am confident I update the python side.
    // The user wants me to implement the NEW strategy, so I will replace this strictly.
    // Wait, the user might still use it? The request is to change the behavior.
    // I'll leave it but implementing it via the new functions just in case.

    // Actually, `generate_bidding_batch` was replaced by `generate_hand_batch`
    // which returns strategies too. And `solve` is separate.
    // So I can't easily reimplement this identically without stitching them back.
    // I will remove it to avoid confusion and compilation errors.
    Err(PyRuntimeError::new_err(
        "This function is deprecated. Use generate_datasets.py workflow.",
    ))
}

#[pyfunction]
fn generate_gameplay_data(path: &str, num_samples: usize) -> PyResult<()> {
    println!("Generating {} gameplay samples to {}...", num_samples, path);
    let start = std::time::Instant::now();

    let (hands, boards, history, trumps, best_cards, best_scores) =
        data_gen::generate_gameplay_batch(num_samples);

    println!("Saving gameplay data to {}...", path);
    write_gameplay_parquet(
        path,
        &hands,
        &boards,
        &history,
        &trumps,
        &best_cards,
        &best_scores,
    )
    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    let duration = start.elapsed();
    println!(
        "Gameplay data generated in {:.2?}. Size: {} bytes",
        duration,
        std::fs::metadata(path)?.len()
    );
    Ok(())
}

/// A Python module implemented in Rust.
#[pymodule]
fn coinche_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<game::GameState>()?;
    m.add_function(wrap_pyfunction!(solve_game, m)?)?;
    m.add_function(wrap_pyfunction!(generate_bidding_hands, m)?)?;
    m.add_function(wrap_pyfunction!(solve_bidding_batch, m)?)?;
    m.add_function(wrap_pyfunction!(generate_gameplay_data, m)?)?;
    Ok(())
}
