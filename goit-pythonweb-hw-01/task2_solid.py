from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Book:
    title: str
    author: str
    year: int


class LibraryInterface(ABC):
    @abstractmethod
    def add_book(self, book: Book) -> None:
        """Add a book to the library."""

    @abstractmethod
    def remove_book(self, title: str) -> bool:
        """Remove a book by title."""

    @abstractmethod
    def get_books(self) -> list[Book]:
        """Return all books from the library."""


class Library(LibraryInterface):
    def __init__(self) -> None:
        self._books: list[Book] = []

    def add_book(self, book: Book) -> None:
        self._books.append(book)

    def remove_book(self, title: str) -> bool:
        for index, book in enumerate(self._books):
            if book.title.lower() == title.lower():
                del self._books[index]
                return True
        return False

    def get_books(self) -> list[Book]:
        return list(self._books)


class LibraryManager:
    def __init__(self, library: LibraryInterface) -> None:
        self._library = library

    def add_book(self, title: str, author: str, year: int) -> None:
        book = Book(title=title, author=author, year=year)
        self._library.add_book(book)
        logger.info('Книгу "%s" додано.', title)

    def remove_book(self, title: str) -> None:
        removed = self._library.remove_book(title)
        if removed:
            logger.info('Книгу "%s" видалено.', title)
            return

        logger.info('Книгу "%s" не знайдено.', title)

    def show_books(self) -> None:
        books = self._library.get_books()
        if not books:
            logger.info("Бібліотека порожня.")
            return

        for book in books:
            logger.info(
                "Title: %s, Author: %s, Year: %s",
                book.title,
                book.author,
                book.year,
            )


def main() -> None:
    library: LibraryInterface = Library()
    manager = LibraryManager(library)

    while True:
        command = input("Enter command (add, remove, show, exit): ").strip().lower()

        match command:
            case "add":
                title = input("Enter book title: ").strip()
                author = input("Enter book author: ").strip()
                year_input = input("Enter book year: ").strip()

                try:
                    year = int(year_input)
                except ValueError:
                    logger.info("Рік має бути цілим числом.")
                    continue

                manager.add_book(title, author, year)
            case "remove":
                title = input("Enter book title to remove: ").strip()
                manager.remove_book(title)
            case "show":
                manager.show_books()
            case "exit":
                logger.info("Завершення роботи.")
                break
            case _:
                logger.info("Invalid command. Please try again.")


if __name__ == "__main__":
    main()
