from dataclasses import dataclass, asdict
from pathlib import Path
import logging
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimEntry:
    timestamp: int = 0
    fleet_evs: float = 0
    fleet_soc: float = 0
    available_evs: int = 0
    charging_evs: int = 0
    vpp_evs: int = 0
    vpp_soc: float = 0
    vpp_charging_power_kw: float = 0


@dataclass()
class ResultEntry:
    timestamp: int = 0
    profit_eur: float = 0
    lost_rentals_eur: float = 0
    lost_rentals_nb: int = 0
    charged_regular_kwh: float = 0
    charged_vpp_kwh: float = 0
    imbalance_kwh: float = 0
    risk_bal: float = 0
    risk_intr: float = 0


class Statistic:
    def __init__(self):
        self.stats = list()

    def add(self, entry):
        self.stats.append(asdict(entry))

    def sum(self):
        df_stats = pd.DataFrame(data=self.stats)
        return df_stats.sum()

    def write(self, filename):
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        df_stats = pd.DataFrame(data=self.stats)
        df_stats = df_stats.round(2)
        df_stats.to_csv(filename, index=False)
        return df_stats
