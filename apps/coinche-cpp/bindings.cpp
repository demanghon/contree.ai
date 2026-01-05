#include "core/cards.hpp"
#include "search/minimax.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

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
}
