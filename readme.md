# Kermit-Coinche: High-Performance AI for Belote Contrée

## 🎯 Motivation

The goal of this project is to build a superhuman Artificial Intelligence for **Belote Contrée** (also known as Coinche). Inspired by the "Kermit" architecture used for the game of Skat, we aim to solve the game using a **Perfect Information Oracle** approach.

Unlike traditional heuristics, our AI learns from a "Double Dummy Solver" — a highly optimized engine that sees all cards and calculates the theoretically optimal score for any given hand. By training a Neural Network to predict this perfect score (Value Network) and the best card to play (Policy Network), we can create an agent that plays at a near-optimal level even with imperfect information.

> For a detailed theoretical analysis and methodology, please refer to the [Research Paper](paper.md).

## 🏗️ Architecture & Methodology

We use a hybrid **Rust + Python + Angular** architecture managed by an **Nx Monorepo**, consisting of the following projects:

### 1. `coinche-engine` (Rust)

The core high-performance Double Dummy Solver and data generator.

- **Role**: Game logic, Minimax solver, Synthetic data generation.
- **Key Dependencies**: `pyo3` (Python bindings), `rayon` (Parallelism), `parquet`/`arrow` (High-efficiency storage).

### 2. `coinche-ml` (Python)

The Machine Learning pipeline for training the agent.

- **Role**: Training Value and Policy networks.
- **Key Dependencies**: `PyTorch 2.0+` (Deep Learning), `Polars`/`Pandas` (Data manipulation).

### 3. `coinche-player` (Angular)

The web-based frontend for human-vs-AI play.

- **Role**: Interactive UI, Game visualization.
- **Key Dependencies**: `Angular`, `Nx`.

### 4. `coinche-runner` (Python)

Scripts for running simulations and benchmarks.

### 5. `coinche-api` (Python)

A standard REST API (FastAPI) to expose the engine features for external clients (e.g. Angular frontend).

- **Role**: Game State Management, API Gateway.
- **Key Dependencies**: `FastAPI`, `Uvicorn`, `Pydantic`.

### Prerequisites

- **Rust**: For the high-performance solver.
  ```bash
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
  ```
- **Python 3.10+**: For Machine Learning and the Runner.
- **Node.js & npm**: For the Nx build system.
- **Maturin**: For Python bindings.
- **Graphviz**: For visualization (optional).
  ```bash
  sudo apt install graphviz
  ```

### Setup

1. **Clone the repository**

   ```bash
   git clone <repo-url>
   cd contree-ai
   ```

2. **Install Global Tools**

   ```bash
   npm install -g nx
   pip install poetry
   ```

3. **Install Project Dependencies**
   ```bash
   npm install
   cd apps/coinche-runner
   poetry install
   cd ../..
   ```

## 🚀 Usage

### Generating Data (Synthetic Datasets)

You can generate synthetic training data using the Rust engine. The data will be saved in Parquet format in `dist/datasets/`.

#### Generate Bidding Data

Generates hand evaluations for the Bidding phase. This process solves 4 full games per sample (one for each trump suit) and is computationally intensive.

```bash
# Basic run (default 50,000 samples)
nx run coinche-engine:generate-bidding-data

# Custom size and thread control (Recommended for memory management)
nx run coinche-engine:generate-bidding-data --samples=10000 --threads=4 --batchSize=1000
```

- **Output**: `dist/datasets/bidding_data.parquet` (merged) and `dist/datasets/bidding_data/` (partitions)
- **Performance**: High CPU/RAM usage. Use `--threads` to limit parallelism if you encounter OOM errors.
- **Arguments**:
  - `--samples`: Total samples to generate (Default: 10,000).
  - `--threads`: CPU threads to use (Default: 4). Lower this if you run out of RAM.
  - `--batchSize`: Samples per solver batch (Default: 2,000). Lower this (e.g., 500) to reduce peak RAM usage.

#### Generate Gameplay Data

Generates decision-making data for the Card Play phase. This simulates partial games and is significantly faster than bidding generation.

```bash
# Basic run (default 10,000 samples, 1 thread)
nx run coinche-engine:generate-gameplay-data

# Fast run (use more threads for speed)
nx run coinche-engine:generate-gameplay-data --samples=100000 --threads=8
```

- **Output**: `dist/datasets/gameplay_data.parquet`
- **Performance**: Low memory usage, scales well with threads. Use higher thread counts for faster generation.
- **Arguments**:
  - `--samples`: Total samples to generate (Default: 10,000).
  - `--threads`: CPU threads to use (Default: 1). Increase this for speed (e.g., 8 or 16).
  - `--batchSize`: Samples per solver batch (Default: 10,000). Control progress update frequency.

### Command Arguments

| Argument      | Description                                           | Default                        | Recommended Usage                                     |
| ------------- | ----------------------------------------------------- | ------------------------------ | ----------------------------------------------------- |
| `--samples`   | Total number of samples to generate.                  | `10,000`                       | Increase to `100,000`+ for training.                  |
| `--threads`   | Number of CPU threads to use.                         | `4` (Bidding) / `1` (Gameplay) | Set to roughly `CPU Cores - 2`. Reduce if OOM occurs. |
| `--batchSize` | Number of hands to solve in one batch (Bidding only). | `2,000`                        | Lower to `500-1000` to reduce RAM usage per thread.   |

> **Note**: These commands use the `maturin` tool to compile the Rust code and then run the Python generation script.

### Running the API Server

To play against the engine via HTTP/JSON (used by the Angular App):

1. **Install Engine & Dependencies**

   ```bash
   # Install engine into current env
   cd apps/coinche-engine && maturin develop && cd ../..

   # Install API dependencies (Pip)
   pip install -r apps/coinche-api/requirements.txt

   # OR Install via Conda
   conda env create -f apps/coinche-api/environment.yml
   conda activate coinche-api
   cd apps/coinche-engine && maturin develop && cd ../..
   ```

2. **Start Server**

   ```bash
   uvicorn apps.coinche-api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **API Documentation**
   Open [http://localhost:8000/docs](http://localhost:8000/docs) to see the Swagger UI.
