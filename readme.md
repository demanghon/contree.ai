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

## 🛠️ Installation & Requirements

### Prerequisites

- **Rust**: For the high-performance solver.
  ```bash
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
  ```
- **Python 3.10+**: For Machine Learning and the Runner.
- **Node.js & npm**: For the Nx build system.
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

Generates hand evaluations for the Bidding phase.

```bash
nx run coinche-engine:generate-bidding-data
```

- **Output**: `dist/datasets/bidding_data.parquet`
- **Default**: 10,000 samples
- **Custom Size**: `nx run coinche-engine:generate-bidding-data --samples=50000`

#### Generate Gameplay Data

Generates decision-making data for the Card Play phase.

```bash
nx run coinche-engine:generate-gameplay-data
```

- **Output**: `dist/datasets/gameplay_data.parquet`
- **Default**: 10,000 samples
- **Custom Size**: `nx run coinche-engine:generate-gameplay-data --samples=50000`

> **Note**: These commands use the `maturin` tool to compile the Rust code and then run the Python generation script.
