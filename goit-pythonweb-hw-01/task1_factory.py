from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class Vehicle(ABC):
    def __init__(self, make: str, model: str) -> None:
        self.make = make
        self.model = model

    @abstractmethod
    def start_engine(self) -> None:
        """Start the vehicle engine."""


class Car(Vehicle):
    def start_engine(self) -> None:
        logger.info("%s %s: Двигун запущено", self.make, self.model)


class Motorcycle(Vehicle):
    def start_engine(self) -> None:
        logger.info("%s %s: Мотор заведено", self.make, self.model)


class VehicleFactory(ABC):
    @abstractmethod
    def create_car(self, make: str, model: str) -> Vehicle:
        """Create a car for a target region."""

    @abstractmethod
    def create_motorcycle(self, make: str, model: str) -> Vehicle:
        """Create a motorcycle for a target region."""


class USVehicleFactory(VehicleFactory):
    def create_car(self, make: str, model: str) -> Vehicle:
        return Car(make, f"{model} (US Spec)")

    def create_motorcycle(self, make: str, model: str) -> Vehicle:
        return Motorcycle(make, f"{model} (US Spec)")


class EUVehicleFactory(VehicleFactory):
    def create_car(self, make: str, model: str) -> Vehicle:
        return Car(make, f"{model} (EU Spec)")

    def create_motorcycle(self, make: str, model: str) -> Vehicle:
        return Motorcycle(make, f"{model} (EU Spec)")


def main() -> None:
    us_factory: VehicleFactory = USVehicleFactory()
    eu_factory: VehicleFactory = EUVehicleFactory()

    vehicles: list[Vehicle] = [
        us_factory.create_car("Ford", "Mustang"),
        us_factory.create_motorcycle("Harley-Davidson", "Sportster"),
        eu_factory.create_car("Volkswagen", "Golf"),
        eu_factory.create_motorcycle("BMW", "R 1250 GS"),
    ]

    for vehicle in vehicles:
        vehicle.start_engine()


if __name__ == "__main__":
    main()
