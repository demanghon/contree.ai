# Coinche Engine (Solver)

This crate implements a high-performance **Double Dummy Solver** for Belote Contrée (Coinche). It is written in Rust for speed and exposes a Python API for easy integration with Machine Learning pipelines.

## 🚀 Core Concepts

### 1. Bitboard Representation
To achieve maximum performance, the game state is not represented by objects or lists, but by **32-bit integers** (Bitboards).
Since Belote has exactly 32 cards, a single `u32` can represent a player's hand.

![Bitboard Diagram](./bitboard_diagram.png)

- **Efficiency**: Checking if a player has a specific suit or a higher trump takes a single CPU cycle (using bitwise `AND`, `OR`, `XOR`).
- **Memory**: The entire game state fits in a few bytes, allowing it to be copied and stored extremely cheaply.

### 2. Minimax with Alpha-Beta Pruning
The solver uses the **Minimax** algorithm to find the theoretically optimal score.
- **Max Node**: The current team tries to maximize their score.
- **Min Node**: The opposing team tries to minimize the current team's score.

**Alpha-Beta Pruning** is used to cut off search branches that are mathematically proven to be inferior. If a move is found that is "too good" for the opponent (beta cutoff), we stop searching that branch immediately.

### 3. Transposition Table
Many different sequences of moves can lead to the exact same game state (e.g., Player A plays King then Ace vs. Ace then King).
- We use **Zobrist Hashing** to assign a unique 64-bit ID to every possible game state.
- We store the result of solved states in a **Transposition Table** (HashMap).
- If the solver encounters a state it has seen before, it retrieves the result instantly instead of re-calculating it.

## 🛠️ Architecture

### `src/game.rs`
Contains the `GameState` struct and core rules logic.
- `get_legal_moves()`: Returns a bitmask of all legal cards to play, handling complex rules like "Must Cut" and "Over-Cut".
- `play_card()`: Updates the state (removes card from hand, adds to trick, updates turn).

### `src/solver.rs`
Contains the search algorithms.
- `solve()`: The entry point.
- `minimax()`: The recursive function implementing Alpha-Beta.

### `src/data_gen/`
Modules for generating synthetic datasets.
- `bidding.rs`: Generates data for the Bidding phase.
- `gameplay.rs`: Generates data for the Card Play phase, using **Bias Sampling** (Endgame/Midgame focus) and **Perturbation** (recovering from mistakes).

## 📦 Python API
This crate is compiled as a Python extension using `maturin`.
```python
import coinche_engine

# Generate 1000 samples of gameplay data
coinche_engine.generate_gameplay_data("data.parquet", 1000)
```
