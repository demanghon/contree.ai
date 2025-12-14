# Comprehensive Research Report: Synthesis and Generation of Supervised Datasets for `Contrée` AI

## 1. Introduction

### 1.1 Objectives
The primary objective of this research is to design and train a state-of-the-art Artificial Intelligence agent for the game of `Contrée`. To overcome the challenges of imperfect information and the lack of high-quality public datasets, this project focuses on a **supervised learning approach** grounded in game-theoretic optimality. 

### 1.2 Rules overview of La Contrée
Belote Contrée is a popular French trick-taking game for 4 players (2 teams of 2).

#### Core Mechanics
- **Deck**: 32 cards (7, 8, 9, 10, Jack, Queen, King, Ace).
- **Teams**: North/South vs. East/West.
- **Objective**: The taking team must score more points than their bid to win the round.

#### Card Values
The values of cards change depending on whether the suit is **Trump (Atout)** or **Non-Trump**.

| Rank | Trump Value | Non-Trump Value |
|------|-------------|-----------------|
| Jack | **20**      | 2               |
| 9    | **14**      | 0               |
| Ace  | 11          | 11              |
| 10   | 10          | 10              |
| King | 4           | 4               |
| Queen| 3           | 3               |
| 8    | 0           | 0               |
| 7    | 0           | 0               |

#### Game Phases

##### Phase 1: Bidding (Enchères)
This is the strategic heart of the game. Players speak in turn to propose a contract.
- **The Contract**: A bid consists of a number (80, 90, ..., 160, or Capot) and a suit (Color, No-Trump, All-Trump).
- **The Goal**: The team must score at least the number of points bid to win.
- **Coinche**: If a player believes the opponents will fail, they can "Coinche" (Double the points). The opponents can "Surcoinche" (Redouble).
- The bidding ends when 3 players pass consecutively.

##### Phase 2: The Play (Jeu de la Carte)
Once the contract is set, the game is played in 8 tricks.
- **Must Follow Suit**: Players must play the suit led if they have it.
- **Cutting (Couper)**: If a player is void in the led suit, they *must* play a Trump (unless their partner is currently winning the trick).
- **Over-Cutting (Surcouper)**: If a Trump has already been played, a player must play a higher Trump if they can.
- **Scoring**: At the end, points are counted. If the contract is fulfilled, the bidding team scores their bid + points made. If not, the defense takes all points (162 + bid).

**Card Values**:
The card hierarchy and point values depend on whether the suit is Trump or Non-Trump:
*   **Trump Suit**: Jack (20), 9 (14), Ace (11), 10 (10), King (4), Queen (3), 8 (0), 7 (0).
*   **Non-Trump Suit**: Ace (11), 10 (10), King (4), Queen (3), Jack (2), 9 (0), 8 (0), 7 (0).
*   **Bonuses**: The winner of the last trick scores an extra 10 points ("Dix de Der"). The "Belote-Rebelote" (King and Queen of trump in hand) awards 20 bonus points.

### 1.3 The Challenge of `Contrée` in Game AI
`Contrée` represents a unique and complex challenge in the field of Game AI. Unlike perfect information games like Chess or Go, where the total game state is visible to both opponents, `Contrée` is an **imperfect information**, zero-sum (for game points) team game. Players only see their own cards and those played on the table, introducing fundamental uncertainty that complicates the direct application of classical search methods.

Furthermore, the **Bidding Phase** introduces a critical cooperative challenge. Unlike the play phase where the goal is purely tactical optimization, bidding requires **implicit communication** with a partner. A bid serves two purposes: proposing a contract and signaling hand strength to the partner. An effective AI must not only evaluate its own hand but also infer its partner's potential and establish a "trust" relationship to reach the optimal contract without overbidding. This adds a layer of **Theory of Mind** and convention learning that is absent in single-player or purely adversarial games.

The goal is to feed a neural network with labeled data $(x, y)$, where $x$ is the player's hand (and potentially history) and $y$ is the theoretical optimal result. Such an approach, known as **Oracle Distillation** or **Student-Teacher Learning**, allows the model to learn the intrinsic value of cards without human biases or exploration errors typical of pure reinforcement learning in early training.

However, a thorough analysis of public databases, code repositories (GitHub), and competition platforms (Kaggle, Hugging Face) reveals a structural absence of pre-calculated datasets for `Contrée` offering this precise "best possible score" metric. While logs of games played by humans or heuristic bots exist, they do not contain the ground truth of mathematical optimality.

## 2. State of the Art and Available Resources

Before proposing a generation solution, it is imperative to examine in detail why current resources are insufficient to meet the demand for "best possible score".

### 2.1 Analysis of GitHub Repositories and Open Source Projects
Several open-source initiatives exist around Belote and `Contrée`, but they mostly focus on environment simulation (for Reinforcement Learning) rather than providing solved data.

#### 2.1.1 The ``Contrée`` Project
The repository identified as [heosaulus/coinche](https://github.com/theosaulus/coinche) is one of the most relevant. It implements an OpenAI Gym-compatible environment, facilitating interaction with reinforcement learning agents.
*   **Value Approach**: The authors attempted to predict hand value for the bidding phase. However, their method involved training a Machine Learning model on "random games".
*   **Limitations**: The average score obtained by random players is radically different from the "best possible score". A model trained on random games will learn a noisy and sub-optimal expected gain, unable to recognize fine strategies like finesses, endplays, or squeezes, which are essential for determining a hand's real potential. This dataset therefore does not meet the optimality requirement.
§
#### 2.1.2 The `belote-ai` Project
This C++ project [eowaaruil/belote-ai](https://github.com/eowaaruil/belote-ai) focuses on game engine implementation and AI matchups. Although C++ is the language of choice for performance (crucial for a solver), the project does not provide a database of solved deals. It serves more as an experimentation platform for real-time tree search algorithms (MCTS).

#### 2.1.3 Comparison with Bridge and Skat
The situation is different in similar games like Bridge or Skat.
*   **Bridge**: Robust libraries like **Bridge Calculator** or **DDS (Double Dummy Solver)** by Bo Haglund exist and are industry standards. Researchers like Mernagh have used databases of 700,000 solved deals provided by Matt Ginsberg (creator of GIB).
*   **Skat**: The German game of Skat (32 cards, 3 players) has solvers like the "Double Dummy Skat Solver" (DDSS). Research on Skat demonstrates that using perfect information solvers to train inference networks is a royal road to performance.

The scarcity of datasets for `Contrée` is explained by the regional nature of the game (mainly France) compared to the universality of Bridge. The `Contrée` AI researcher must therefore borrow methodologies from Bridge and adapt them, rather than looking for an "off-the-shelf" dataset.

### 2.2 Generalist Databases (Kaggle, Hugging Face)
Searches on Kaggle and Hugging Face confirm this shortage.
*   **Hugging Face**: Datasets available under "card games" tags often concern image processing (card detection) or text (game rules), but not logs of solved games.
*   **Kaggle**: Datasets for Poker (Texas Hold'em hands) or fraud detection can be found, but the specific structure of `Contrée` (tricks, trumps, announcements) is absent.

**Partial Conclusion**: There is currently no public dataset containing the "best possible score" for `Contrée`. The solution lies in synthesizing data via an ad hoc solver.



## 3. Theoretical Framework: From Imperfect Information to Oracle

To address the challenge of `Contrée`, we propose a robust model building pipeline consisting of three distinct stages:
1.  **Solver Creation**: Developing a **Double Dummy Solver** (Oracle) that solves the game with perfect information to establish a ground truth.
2.  **Dataset Generation**: Using this solver to generate a massive synthetic dataset where millions of deals are labeled for both the **Bidding Phase** (evaluating expected score) and the **Game Phase** (identifying the optimal card).
3.  **Model Training**: Training specialized Neural Networks to approximate the Oracle's output, effectively distilling perfect information knowledge into an agent that operates under imperfect information.

To understand how to generate this dataset, we must precisely define what "best possible score" means in an algorithmic context.

## 4. Solver Design

### 4.1 The Double Dummy Concept
In trick-taking game literature, the problem of finding the best possible score when all cards are known is called the **Double Dummy** problem.
*   **Hypothesis**: We assume each player knows the position of all cards (theirs and opponents').
*   **Execution**: Players execute moves that maximize their gain (for the attacking team) or minimize loss (for the defending team).
*   **Result**: The score obtained under these conditions is the **Minimax value** of the game state. It is a theoretical upper bound on performance.

### 4.2 Minimax Algorithm and Alpha-Beta Pruning
To calculate this score, we use the Minimax algorithm. Since `Contrée` is a zero-sum game (162 total points + announcements), what Team A wins, Team B loses (or fails to win).
The algorithm explores the tree of possibilities:
*   **Max Node**: It is Team A's turn. They choose the card leading to the future state with the highest value.
*   **Min Node**: It is Team B's turn. They choose the card leading to the future state with the lowest value for Team A.

The raw state space for 32 cards is $32!$, which is gigantic. However, `Contrée` rules (must follow, must cut, over-cut) drastically reduce the effective branching factor. Furthermore, using **Alpha-Beta Pruning** avoids exploring branches proven to be sub-optimal.

### 3.3 Relevance for Supervised Learning
Why train a model on "Double Dummy" data when the real game has hidden information?
*   **Learning Card Value**: The model implicitly learns the relative strength of cards. It learns that an Ace is strong, but a 10 is weak if the Ace hasn't been played.
*   **Strategy Fusion Problem**: This is a critical point raised in research. A Double Dummy solver adapts its strategy to the specific distribution of opponent cards. A human player cannot.
    *   *Example*: If the solver sees the King in East, it will finesse. If it sees it in West, it will play the Ace. The neural network, not seeing the King, will sometimes receive the instruction "finesse" and sometimes "play Ace" for the same visible hand.
    *   *Solution*: By averaging these instructions over millions of deals, the network learns the **Mathematical Expectation** of the gain. If the finesse works 50% of the time, the network will learn an intermediate value, which is exactly the desired behavior for a robust player.

## 4. Dataset Generation Methodology (The "Generator")



## 4. Dataset Generation Methodology

### 4.1 Introduction and Rationale
The core of our supervised learning approach relies on the **distillation** of an Oracle (the Double Dummy Solver) into a Neural Network. A naive approach would be to generate millions of uniform random deals. However, this method is fundamentally flawed for high-level play due to the **sparsity of strategic events**.
In *Contrée*, critical scenarios like "Capots" (Slams), specific end-game squeezes, or delicate defensive signals occur with negligible probability ($<0.1\%$) in random deals. A model trained on uniform data would statistically ignore these events, treating them as outliers or noise, and thus fail to learn the precise strategies required to handle them.
To overcome this, we employ **Importance Sampling** and **biased generation** strategies. The goal is not to represent the statistical reality of the game, but to over-represent the "boundary cases" where the model must extract a signal.

### 4.2 Bidding Phase Generation (Value Network)
**Objective**: Train a Value Network $V(hand, trump) \rightarrow \mathbb{R}$ predicting the expected points.

**Biased Sampling Strategy**:
We employ a mixture of generators to ensure the manifold of possible hands is adequately covered, particularly in high-value regions.
*   **Uniform Random (40%)**: Serves as a regularizer to ensure the model handles "average" mostly pass-out hands correctly.
*   **Force Capot (20%)**:
    *   *Implementation*: Deterministically dealing the top 5 trumps and outside Aces to one player.
    *   *Rationale*: A "Capot" is worth 252 points, dwarfing a normal game (82 points). Without this bias, the L2 Loss function would under-prioritize these rare hands. The model must explicitly learn to recognize the geometric pattern of a "perfect hand".
*   **Force Belote (20%)**:
    *   *Implementation*: Constructing hands with (King, Queen) of trump.
    *   *Rationale*: Teaches the specific +20 point bonus and the tactical value of holding strict control of the trump suit.
*   **Distributional Shaping (20%)**:
    *   *Implementation*: Forcing specific suit distributions (e.g., `6-3-2-1` or `5-5-2-1`) regardless of card rank.
    *   *Rationale*: Evaluation relies heavily on "shape" (voids, singletons) for ruffing power. This bias decorrelates "High Card Points" from "Distributional Points", preventing the model from overly relying on Aces and Kings.

### 4.3 Gameplay Phase Generation (Policy Network)
**Objective**: Train a Policy Network $\pi(state) \rightarrow action$ predicting the optimal move from the Oracle.

**4.3.1 Temporal Bias (Curriculum by Starting Point)**
We do not simulate full games from move 0 to 32 uniformly.
*   **Endgame Focus (50% - Tricks 6-8)**: The "horizon" is short, allowing the solver to be perfectly accurate and the logic to be purely mathematical (counting cards). This provides a noise-free ground truth for basic mechanics.
*   **Midgame (30%)** and **Opening (20%)**: These positions are more computationally expensive to generate. By undersampling openings, we optimize the computational budget while still providing examples of long-term planning.

**4.3.2 Critical Decision Filtering (Variance Reduction)**
A significant optimization is the removal of "trivial" samples.
*   *Method*: For a given state $s$, we compute the score of the best move $m^*$ and the second-best move $m^{2nd}$.
*   *Criterion*: If $Score(m^*) - Score(m^{2nd}) = 0$, the sample is **discarded**.
*   *Rationale*: If multiple cards lead to the exact same outcome, the decision contains no strategic signal (e.g., playing an 8 or a 7 on a master Ace). Training on such data introduces label noise (`8` is a target, `7` is not, despite being equal). Filtering ensures we only train on **discriminative** positions.

**4.3.3 Perturbation and Recovery (Interventional Learning)**
*   *Method*: With probability $p=0.2$, the generator forces the player to play a *sub-optimal* move, updates the state, and *then* asks the solver for the optimal followup.
*   *Rationale*: This mimics the **DAgger** (Dataset Aggregation) approach. It exposes the model to off-policy states—situations where a mistake has already been made—teaching it how to mitigate losses (defensive recovery) rather than assuming perfect play has occurred up to that point.

### 4.4 Dataset Size Estimation
A crucial question for resource planning is: *How many samples are needed?*
Since *Contrée* (32 cards) has a significantly smaller state space than Bridge (52 cards), but retains high complexity, we can derive estimates from comparative literature (e.g., *AlphaBridge* or *Nannerl*).

*   **Bidding Dataset**: \approx **5 Million Samples**.
    *   *Justification*: The number of abstract "hand patterns" is limited, but the combination of high cards within those patterns is vast. 5 million samples allow showing every major distribution type ~50,000 times with varying strength. This is sufficient for a Value Network to converge to a low MSE.
*   **Gameplay Dataset**: \approx **20 Million Decision Points**.
    *   *Justification*: A full game involves ~32 moves. However, due to our "Critical Filtering", we might only keep ~8 meaningful decisions per game.
    *   Generating 20M meaningful decisions (equivalent to ~2.5M full games) ensures that the network sees rare end-game alignments and complex squeeze patterns enough times to generalize.
    *   *Note*: Experience in similar domains suggests that "10M is a baseline, 100M is State-of-the-Art". Given our compute constraints, 20M is a pragmatic target that usually yields near-human performance.
