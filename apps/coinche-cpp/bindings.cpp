#include "core/cards.hpp"
#include "search/minimax.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace py = pybind11;
using namespace cointree;

// Wrapper for Python List[List[Card]] -> std::array<CardSet, 4>
int solve_wrapper(std::vector<std::vector<Card>> py_hands, Suit contract_suit,
                  int contract_player,
                  std::vector<std::pair<int, Card>> current_trick,
                  int starter_player, int ns_points, int ew_points) {
  if (py_hands.size() != 4)
    throw std::runtime_error("Must provide 4 hands");

  std::array<CardSet, 4> hands;
  for (int i = 0; i < 4; ++i) {
    for (const auto &c : py_hands[i]) {
      hands[i].add(c);
    }
  }

  MinimaxSolver solver;
  return solver.solve(hands, contract_suit, contract_player,
                      current_trick, starter_player, ns_points, ew_points);
}

// Wrapper for solving all 4 suits
std::map<Suit, int> solve_all_suits_wrapper(
    std::vector<std::vector<Card>> py_hands,
    int contract_player, std::vector<std::pair<int, Card>> current_trick,
    int starter_player, int ns_points, int ew_points) {

  if (py_hands.size() != 4)
    throw std::runtime_error("Must provide 4 hands");

  // Parse Hands Once
  std::array<CardSet, 4> hands;
  for (int i = 0; i < 4; ++i) {
    for (const auto &c : py_hands[i]) {
      hands[i].add(c);
    }
  }

  MinimaxSolver solver; // Shared instance (TT is reused)
  std::map<Suit, int> results;

  // We iterate 0..3 (Suits)
  for (int s = 0; s < 4; ++s) {
    Suit trump = static_cast<Suit>(s);
    // Note: We use the same 'contract_amount' for all, or 80 default?
    // The user input signature doesn't specify per-suit amount.
    // Assuming we just want to know "if trump is X, what is max score?"
    // Pass same other params.
    int score = solver.solve(hands, trump, contract_player,
                             current_trick, starter_player, ns_points, ew_points);
    results[trump] = score;
  }

  return results;
}

// Batch Solver: List[List[List[Card]]] -> Numpy Array [N, 4]
// Returns scores for [Hearts, Diamonds, Clubs, Spades] for each hand
py::array_t<int> solve_batch(std::vector<std::vector<std::vector<Card>>> batch_games,
                             int contract_player) {
  int N = batch_games.size();
  if (N == 0) return py::array_t<int>();

  // 1. Prepare Data in C++ friendly format (Main Thread)
  // We parsed Python objects into std::vector<std::vector<std::vector<Card>>> automatically by pybind11
  // Now flatten or just process directly.
  
  // We need to construct CardSet for each player for each game.
  struct GameState {
    std::array<CardSet, 4> hands;
  };
  
  std::vector<GameState> games(N);
  for(int i=0; i<N; ++i) {
    if(batch_games[i].size() != 4) throw std::runtime_error("Each game must have 4 hands");
    for(int p=0; p<4; ++p) {
      for(const auto& c : batch_games[i][p]) {
        games[i].hands[p].add(c);
      }
    }
  }

  // 2. Allocate Result Array
  auto results = py::array_t<int>(N * 4);
  py::buffer_info buf = results.request();
  int* ptr = static_cast<int*>(buf.ptr);

// 3. Parallel Solve
#ifdef _OPENMP
  #pragma omp parallel
#endif
  {
    // Thread-Local Solver (Persistent TT per thread logic)
    MinimaxSolver solver;
    std::vector<std::pair<int, Card>> empty_trick; 
    empty_trick.reserve(4);

#ifdef _OPENMP
    #pragma omp for
#endif
    for(int i=0; i<N; ++i) {
        for(int s=0; s<4; ++s) { // HEARTS, DIAMONDS, CLUBS, SPADES
            // solve() args: hands, contract_suit, contract_player, current_trick, starter_player, ns_points, ew_points
            // Assuming clean start: trick empty, starter=0, points=0
            int score = solver.solve(games[i].hands, (Suit)s, contract_player, empty_trick, 0, 0, 0);
            ptr[i * 4 + s] = score;
        }
    }
  }

  // Reshape to (N, 4)
  results.resize({N, 4});
  return results;
}

PYBIND11_MODULE(cointree_cpp, m) {
  m.doc() = "High-performance C++ Engine for Coinche";

  py::enum_<Suit>(m, "Suit")
      .value("HEARTS", Suit::HEARTS)
      .value("DIAMONDS", Suit::DIAMONDS)
      .value("CLUBS", Suit::CLUBS)
      .value("SPADES", Suit::SPADES)
      .value("NONE", Suit::NONE);

  py::enum_<Rank>(m, "Rank")
      .value("SEVEN", Rank::SEVEN)
      .value("EIGHT", Rank::EIGHT)
      .value("NINE", Rank::NINE)
      .value("TEN", Rank::TEN)
      .value("JACK", Rank::JACK)
      .value("QUEEN", Rank::QUEEN)
      .value("KING", Rank::KING)
      .value("ACE", Rank::ACE);

  py::class_<Card>(m, "Card")
      .def(py::init<uint8_t>())
      .def(py::init<Suit, Rank>())
      .def_readonly("id", &Card::id)
      .def("suit", &Card::suit)
      .def("rank", &Card::rank)
      .def("strength", &Card::strength)
      .def("points", &Card::points)
      .def("__repr__", &Card::toString)
      .def("__eq__", &Card::operator==)
      .def("__hash__", [](const Card &c) { return c.id; });

  py::class_<MinimaxSolver>(m, "MinimaxSolver")
      .def(py::init<>())
      .def("solve", &solve_wrapper);

  m.def("solve_game", &solve_wrapper,
        "Solves the game state using C++ Minimax. Returns the score of the "
        "contract team.");

  m.def("solve_all_suits", &solve_all_suits_wrapper,
        "Solves the game for all 4 suits (HEARTS, DIAMONDS, CLUBS, SPADES). "
        "Returns a dict {Suit: score}.");

  m.def("solve_batch", &solve_batch,
        "Solves a batch of hands for all 4 suits in parallel. "
        "Returns a NumPy array of shape (N, 4).",
        py::arg("batch_games"), py::arg("contract_player") = 0);
}
