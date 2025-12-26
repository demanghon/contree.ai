mod data_gen;
pub mod gameplay;
mod solver;

use data_gen::{
    generate_hand_batch, generate_raw_gameplay_batch as gen_raw_gameplay_impl,
    solve_gameplay_batch as solve_gameplay_impl, solve_hand_batch,
};
use gameplay::playing::PlayingState;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use solver::solve;

#[pyfunction]
fn solve_game(state: &PlayingState) -> PyResult<(i16, u8)> {
    let (score, best_move) = solve(state, false);
    Ok((score, best_move))
}

#[pyfunction]
fn generate_bidding_hands(num_samples: usize) -> PyResult<(Vec<u32>, Vec<u8>)> {
    let (hands, strategies) = generate_hand_batch(num_samples);
    Ok((hands, strategies))
}

#[pyfunction]
fn solve_bidding_batch(py: Python, hands: Vec<u32>) -> PyResult<Vec<Vec<i16>>> {
    py.allow_threads(|| {
        let scores = solve_hand_batch(hands);
        Ok(scores)
    })
}

#[pyfunction]
fn generate_bidding_data(path: String, num_samples: usize) -> PyResult<()> {
    // This function is deprecated
    Err(PyRuntimeError::new_err(
        "This function is deprecated. Use generate_datasets.py workflow.",
    ))
}

#[pyfunction]
fn generate_raw_gameplay_batch(
    py: Python,
    num_samples: usize,
) -> PyResult<(
    Vec<u32>,
    Vec<Vec<u8>>,
    Vec<u32>,
    Vec<u8>,
    Vec<Vec<u8>>,
    Vec<u8>,
)> {
    py.allow_threads(|| {
        let (hands, boards, history, trumps, tricks_won, players) =
            gen_raw_gameplay_impl(num_samples);
        Ok((hands, boards, history, trumps, tricks_won, players))
    })
}

#[pyfunction]
fn solve_gameplay_batch(
    py: Python,
    hands: Vec<u32>,
    boards: Vec<Vec<u8>>,
    history: Vec<u32>,
    trumps: Vec<u8>,
    tricks_won: Vec<Vec<u8>>,
    players: Vec<u8>,
) -> PyResult<(Vec<u8>, Vec<i16>, Vec<bool>)> {
    py.allow_threads(|| {
        let (best_cards, best_scores, valid) =
            solve_gameplay_impl(hands, boards, history, trumps, tricks_won, players);
        Ok((best_cards, best_scores, valid))
    })
}

/// A Python module implemented in Rust.
#[pymodule]
fn coinche_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<gameplay::playing::PlayingState>()?;
    m.add_function(wrap_pyfunction!(solve_game, m)?)?;
    m.add_function(wrap_pyfunction!(generate_bidding_hands, m)?)?;
    m.add_function(wrap_pyfunction!(solve_bidding_batch, m)?)?;
    m.add_function(wrap_pyfunction!(generate_raw_gameplay_batch, m)?)?;
    m.add_function(wrap_pyfunction!(solve_gameplay_batch, m)?)?;
    Ok(())
}
