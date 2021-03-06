from datetime import datetime
import logging
import simpy


class EV:
    def __init__(self, env, vpp, name, soc, battery_capacity, charging_speed):
        self.logger = logging.getLogger(__name__)

        # Battery capacity in percent
        self.battery = simpy.Container(env, init=soc, capacity=100)
        self.env = env
        self.name = name
        self.vpp = vpp
        self.action = None

        self.charging_step = self._charging_step(battery_capacity, charging_speed, 5)

        self.available = True
        self.charging = False

        self.log("Added to fleet!")

    def __repr__(self):
        return repr((self.name, round(self.battery.level, 1)))

    def log(self, message, level=None):
        if level is None:
            level = self.logger.info

        level(
            "[%s] - %s(%.2f/%s) %s"
            % (
                datetime.fromtimestamp(self.env.now),
                self.name,
                self.battery.level,
                self.battery.capacity,
                message,
            )
        )

    def debug(self, message):
        self.log(message, self.logger.debug)

    def error(self, message):
        self.log(message, self.logger.error)

    def warning(self, message):
        self.log(message, self.logger.warning)

    def charge_timestep(self):
        increment = min(self.charging_step, self.battery.capacity - self.battery.level)
        if increment > 0:
            self.battery.put(increment)
        self.log("Charged battery for %.2f%%." % increment)

        # Remove EV after from VPP when battery too full
        if (
            self.battery.capacity - self.battery.level < self.charging_step
            and self.vpp.contains(self)
        ):
            self.debug("Remove from VPP. Too full!")
            self.vpp.remove(self)

    def drive(
        self,
        rental,
        duration,
        trip_charge,
        end_charger,
        trip_price,
        account,
        refuse=True,
    ):
        self.log("Starting trip %d." % rental)

        # 1. Check if enough battery for trip left
        if trip_charge > 0 and self.battery.level < trip_charge:
            self.error("Not enough battery for the planned trip %d!" % rental)
            self.log(
                "Account for lost profits of %.2f EUR. Current balance %.2f EUR."
                % (trip_price, account.balance)
            )
            account.subtract(trip_price)
            account.lost_rental(trip_price)
            return

        # TODO: Check overcommitments with perfect benchmark strategy
        # 2. Refuse rental if other EVs in VPP can not substitute capacity
        if (
            refuse
            and self.vpp.contains(self)
            and self.vpp.commited_capacity > self.vpp.capacity()
        ):
            self.log(
                (
                    "Refusing rental! "
                    "EV is commited to VPP and no replacement EV is available."
                )
            )
            self.log(
                "Account for lost profits of %.2f EUR. Current balance %.2f EUR."
                % (trip_price, account.balance)
            )
            account.subtract(trip_price)
            account.lost_rental(trip_price)
            return

        # 3. Remove EV from VPP if allocated to it
        if self.vpp.contains(self):
            self.vpp.remove(self)

        # 4. Drive for the trip duration
        # NOTE: Arrive one second early, to be able to start again
        self.available = False
        self.charging = False
        yield self.env.timeout((duration * 60) - 1)  # seconds
        account.rental(trip_price)
        self.available = True

        # 5. Adjust SoC
        self.log(
            "End Trip %d: Drove for %.2f minutes and consumed %s%% charge."
            % (rental, duration, trip_charge)
        )
        self.log("Adjusting battery level...")
        yield self.env.process(self._adjust_soc(trip_charge))

        # 6. Add to VPP when parked at charger
        if end_charger == 1:
            self.log("At a charging station!")
            self.charging = True

            # Only add to VPP if enough battery capacity to charge next timeslot
            if self.battery.capacity - self.battery.level >= self.charging_step:
                self.vpp.add(self)
            else:
                self.vpp.log(
                    "Not adding EV %s to VPP, not enough free battery capacity(%.2f)"
                    % (self.name, self.battery.capacity - self.battery.level)
                )

        else:
            self.log("Parked where no charger around")

    def _adjust_soc(self, trip_charge):
        """
            Adjusts the EVs State of Charge according to the trip charge.
            Handles special cases and data irregularities.
        """

        # Special case: Battery has been charged without beeing at the charger
        if trip_charge < 0:
            self.log(
                "EV was already at charging station. Battery level: %d. Trip charge: %d"
                % (self.battery.level, trip_charge)
            )

            # Charged during the trip:  More than possible
            free_battery = self.battery.capacity - self.battery.level
            if free_battery > 0 and -trip_charge >= free_battery:
                yield self.battery.put(self.battery.capacity - self.battery.level)
                self.log("Battery charged more than available space. Filled up to 100.")
            # Charged during the trip: Adjust level
            elif -trip_charge < free_battery:
                yield self.battery.put(-trip_charge)
                self.log("Battery level has been increased by %s%%." % -trip_charge)
            else:
                self.log("Battery is still full")
        # Special case: No used SoC
        elif trip_charge == 0:
            self.log("No consumed charge!")
        # Normal SoC usage
        else:
            yield self.battery.get(trip_charge)
            self.log("Battery level has been decreased by %s%%." % trip_charge)

    def _charging_step(self, battery_capacity, charging_speed, control_period):
        """ Returns the SoC increase given the control period in minutes """

        kwh_per_control_period = (charging_speed / 60) * control_period
        soc_per_control_period = 100 * kwh_per_control_period / battery_capacity
        return soc_per_control_period
