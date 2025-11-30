export class CardModel {
    constructor(
        public id: number,
        public color: string,
        public suit: string,
        public label: string
    ) { }
}

export const DECK: CardModel[] = [
    new CardModel(0, 'black', '♠', '7'),
    new CardModel(1, 'black', '♠', '8'),
    new CardModel(2, 'black', '♠', '9'),
    new CardModel(3, 'black', '♠', '10'),
    new CardModel(4, 'black', '♠', 'J'),
    new CardModel(5, 'black', '♠', 'Q'),
    new CardModel(6, 'black', '♠', 'K'),
    new CardModel(7, 'black', '♠', 'A'),
    new CardModel(8, 'red', '♥', '7'),
    new CardModel(9, 'red', '♥', '8'),
    new CardModel(10, 'red', '♥', '9'),
    new CardModel(11, 'red', '♥', '10'),
    new CardModel(12, 'red', '♥', 'J'),
    new CardModel(13, 'red', '♥', 'Q'),
    new CardModel(14, 'red', '♥', 'K'),
    new CardModel(15, 'red', '♥', 'A'),
    new CardModel(16, 'black', '♣', '7'),
    new CardModel(17, 'black', '♣', '8'),
    new CardModel(18, 'black', '♣', '9'),
    new CardModel(19, 'black', '♣', '10'),
    new CardModel(20, 'black', '♣', 'J'),
    new CardModel(21, 'black', '♣', 'Q'),
    new CardModel(22, 'black', '♣', 'K'),
    new CardModel(23, 'black', '♣', 'A'),
    new CardModel(24, 'red', '♦', '7'),
    new CardModel(25, 'red', '♦', '8'),
    new CardModel(26, 'red', '♦', '9'),
    new CardModel(27, 'red', '♦', '10'),
    new CardModel(28, 'red', '♦', 'J'),
    new CardModel(29, 'red', '♦', 'Q'),
    new CardModel(30, 'red', '♦', 'K'),
    new CardModel(31, 'red', '♦', 'A'),
];

export const getCardById = (id: number): CardModel | null => {
    if (id < 0 || id >= DECK.length) return null;
    return DECK[id];
};
