Project Specification: "Kermit-Coinche" - High-Performance Belote AI

I want to build a superhuman AI for the French card game "Belote Contrée" (Coinche). The architecture is inspired by the "Kermit" project (originally for Skat): a hybrid system using a high-performance Rust solver (Oracle) to generate training data for a Python Neural Network.

Please act as a Senior Software Architect and help me scaffold this project within an Nx Monorepo.
1. The Domain: Rules of "La Contrée"

This is a 4-player trick-taking game (2 vs 2).

    Deck: 32 cards (7, 8, 9, 10, Jack, Queen, King, Ace).

    Card Values:

        Trump (Atout): Jack (20), 9 (14), Ace (11), 10 (10), K (4), Q (3), 8 (0), 7 (0).

        Non-Trump: Ace (11), 10 (10), K (4), Q (3), J (2), 9 (0), 8 (0), 7 (0).

    Total Points: 162 points per deal (152 card points + 10 for the last trick called "Dix de Der").

    The Crucial Rule (Points Annoncés):

        The game has a bidding phase where a team promises to make X points (e.g., "100 Spades").

        To win, the team must score >= X points.

        However, for the Solver, we need to calculate the Raw Points (0-162) achievable given optimal play. The "Winning/Losing" logic is applied later based on the bid.

2. Technical Architecture
A. The Engine (Rust) - libs/coinche-solver

This is the performance bottleneck. It must be written in Rust and exposed to Python via PyO3.

    Representation: Use Bitboards (u32 or u64) to represent hands. This is mandatory for performance.

    Oracle: Implement a Double Dummy Solver (Minimax with Alpha-Beta pruning).

        Input: 4 known hands, current trick history, trump suit.

        Output: The exact number of points the current player's team will score assuming perfect play from everyone.

    PIMC Wrapper: Implement a function that takes a hidden hand, generates N random consistent worlds, solves them, and averages the results (Perfect Information Monte Carlo).

B. The ML Pipeline (Python) - apps/ml-trainer

    Generator: A script that generates millions of random deals, calls the Rust Oracle to get the ground truth score (Label), and saves the data.

    Format: Save data as Parquet files (efficient storage).

    Model: A supervised learning model (PyTorch) that learns to predict:

        Value: The expected score (0-162) given a hand (for bidding).

        Policy: The best card to play given a history.

3. Project Structure (Nx Monorepo)

We will use Nx to manage the workspace.

    /apps/trainer: Python application for training (Poetry/uv).

    /libs/solver: Rust library (Cargo) managed via maturin for Python bindings.

4. Your Task

Please initialize the project structure and provide the code for the Core Rust Engine.

    Define the Card, Suit, and GameState structs in Rust using Bitmasking/Bitboards.

    Implement the move_generator (handling constraints: must follow suit, must cut, must over-cut).

    Show how to expose a solve(north, east, south, west, trump) function to Python using PyO3.