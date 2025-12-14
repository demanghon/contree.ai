---
description: Create a Coinche AI Player
---

This workflow guides you through the process of creating an AI player for the game of Coinche (La Contrée).

1.  **Define the Goal**: You want to create an AI agent capable of playing Coinche at a high level.
2.  **Generate Training Data**:
    -   Use the `coinche-engine` to generate synthetic datasets (Double Dummy Solver).
    -   Run `nx run coinche-engine:generate-bidding-data` to create bidding data.
    -   Run `nx run coinche-engine:generate-gameplay-data` to create gameplay data.
3.  **Train the Model**:
    -   Use `apps/coinche-ml` to train neural networks.
    -   Train a **Value Network** for bidding (predicting hand potential).
    -   Train a **Policy Network** for card play (predicting optimal moves).
4.  **Integrate the Player**:
    -   Create a new player implementation in `apps/coinche-player`.
    -   Load the trained models (ONNX or TensorFlow Lite).
    -   Implement the `Player` interface to use the models for decision making.
5.  **Evaluate**:
    -   Play against the Double Dummy Solver (Oracle) to measure optimality gap.
    -   Play against heuristic bots or human players.

// turbo
6.  Check if `apps/coinche-ml` is configured.
