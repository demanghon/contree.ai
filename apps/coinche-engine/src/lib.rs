mod data_gen;
mod game;
mod solver;

use data_gen::{generate_bidding_batch, write_bidding_parquet};
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
fn generate_bidding_data(path: String, num_samples: usize) -> PyResult<()> {
    println!("Generating {} bidding samples to {}...", num_samples, path);
    let (hands, scores) = generate_bidding_batch(num_samples);
    println!("Saving bidding data to {}...", path);
    write_bidding_parquet(&path, &hands, &scores);
    Ok(())
}

#[pyfunction]
fn generate_gameplay_data(path: &str, num_samples: usize) -> PyResult<()> {
    println!("Generating {} gameplay samples to {}...", num_samples, path);
    let start = std::time::Instant::now();

    let (hands, boards, history, trumps, best_cards, best_scores) =
        data_gen::generate_gameplay_batch(num_samples);

    println!("Saving gameplay data to {}...", path);
    data_gen::write_gameplay_parquet(
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
    m.add_function(wrap_pyfunction!(generate_bidding_data, m)?)?;
    m.add_function(wrap_pyfunction!(generate_gameplay_data, m)?)?;
    Ok(())
}
