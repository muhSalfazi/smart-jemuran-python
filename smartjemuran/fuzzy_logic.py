import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from typing import Dict
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class FuzzySystem:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FuzzySystem, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        try:
            # Input variables
            self.temperature = ctrl.Antecedent(np.arange(0, 50, 1), 'temperature')
            self.humidity = ctrl.Antecedent(np.arange(0, 100, 1), 'humidity')
            self.light = ctrl.Antecedent(np.arange(0, 4096, 1), 'light')
            self.rain = ctrl.Antecedent(np.arange(0, 2, 1), 'rain')
            self.time = ctrl.Antecedent(np.arange(0, 24, 1), 'time')

            # Output variable
            self.recommendation = ctrl.Consequent(np.arange(0, 101, 1), 'recommendation')

            # Membership functions
            self._setup_membership_functions()
            self._setup_rules()

            self.control_system = ctrl.ControlSystem(self.rules)
            self.simulation = ctrl.ControlSystemSimulation(self.control_system)
            
            logger.info("Fuzzy system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize fuzzy system: {str(e)}", exc_info=True)
            raise

    def _setup_membership_functions(self):
        """Setup membership functions"""
        try:
            # Temperature
            self.temperature['cold'] = fuzz.trapmf(self.temperature.universe, [0, 0, 15, 22])
            self.temperature['normal'] = fuzz.trimf(self.temperature.universe, [20, 25, 30])
            self.temperature['hot'] = fuzz.trapmf(self.temperature.universe, [28, 32, 50, 50])

            # Humidity
            self.humidity['dry'] = fuzz.trapmf(self.humidity.universe, [0, 0, 30, 50])
            self.humidity['normal'] = fuzz.trimf(self.humidity.universe, [40, 60, 80])
            self.humidity['humid'] = fuzz.trapmf(self.humidity.universe, [70, 80, 100, 100])

            # Light
            self.light['dark'] = fuzz.trapmf(self.light.universe, [2500, 3000, 4096, 4096])
            self.light['medium'] = fuzz.trimf(self.light.universe, [1000, 2000, 3000])
            self.light['bright'] = fuzz.trapmf(self.light.universe, [0, 0, 1500, 2000])

            # Rain
            self.rain['no_rain'] = fuzz.trimf(self.rain.universe, [0, 0, 0.5])
            self.rain['rain'] = fuzz.trimf(self.rain.universe, [0.5, 1, 1])

            # Time
            self.time['morning'] = fuzz.trapmf(self.time.universe, [5, 7, 10, 12])
            self.time['afternoon'] = fuzz.trapmf(self.time.universe, [10, 12, 15, 17])
            self.time['evening'] = fuzz.trapmf(self.time.universe, [15, 17, 19, 21])
            self.time['night'] = fuzz.trapmf(self.time.universe, [19, 21, 23, 24])

            # Recommendation
            self.recommendation['bad'] = fuzz.trimf(self.recommendation.universe, [0, 0, 30])
            self.recommendation['fair'] = fuzz.trimf(self.recommendation.universe, [20, 50, 80])
            self.recommendation['good'] = fuzz.trimf(self.recommendation.universe, [70, 100, 100])
        except Exception as e:
            logger.error(f"Error setting up membership functions: {str(e)}", exc_info=True)
            raise

    def _setup_rules(self):
        """Setup fuzzy rules"""
        try:
            self.rules = [
                # Rule 1: If raining, bad recommendation
                ctrl.Rule(self.rain['rain'], self.recommendation['bad']),

                # Rule 2: If night time, bad recommendation
                ctrl.Rule(self.rain['no_rain'] & self.time['night'], 
                         self.recommendation['bad']),

                # Rule 3: Ideal conditions
                ctrl.Rule(
                    self.rain['no_rain'] &
                    self.time['afternoon'] &
                    self.temperature['normal'] &
                    self.humidity['normal'] &
                    self.light['bright'],
                    self.recommendation['good']
                ),

                # Rule 4: Fair conditions
                ctrl.Rule(
                    self.rain['no_rain'] &
                    (self.time['morning'] | self.time['evening']) &
                    (self.temperature['normal'] | self.temperature['hot']) &
                    self.humidity['normal'],
                    self.recommendation['fair']
                ),

                # Rule 5: Medium light or high humidity
                ctrl.Rule(
                    self.rain['no_rain'] &
                    (self.light['medium'] | self.humidity['humid']),
                    self.recommendation['fair']
                ),

                # Rule 6: Cold temperature with high humidity
                ctrl.Rule(
                    self.temperature['cold'] & self.humidity['humid'],
                    self.recommendation['bad']
                ),
                
                # Default rule
                ctrl.Rule(
                    self.rain['no_rain'],
                    self.recommendation['fair']
                )
            ]
        except Exception as e:
            logger.error(f"Error setting up rules: {str(e)}", exc_info=True)
            raise

    def evaluate(self, temperature: float, humidity: float, light: int, rain: int, time: int) -> Dict:
        """Evaluate drying conditions"""
        try:
            logger.info(f"Evaluating - temp: {temperature}, humidity: {humidity}, "
                      f"light: {light}, rain: {rain}, time: {time}")

            # Input validation
            if not (0 <= temperature <= 50):
                raise ValueError("Temperature must be between 0-50°C")
            if not (0 <= humidity <= 100):
                raise ValueError("Humidity must be between 0-100%")
            if not (0 <= light <= 4096):
                light = max(0, min(light, 4096))
                logger.warning(f"Light value clamped to {light}")
            if rain not in (0, 1):
                rain = 1 if rain else 0
                logger.warning(f"Rain value converted to {rain}")
            if not (0 <= time < 24):
                time = time % 24
                logger.warning(f"Time normalized to {time}")

            # Set inputs
            self.simulation.input['temperature'] = float(temperature)
            self.simulation.input['humidity'] = float(humidity)
            self.simulation.input['light'] = float(light)
            self.simulation.input['rain'] = float(rain)
            self.simulation.input['time'] = float(time)
            
            self.simulation.compute()
            
            if 'recommendation' not in self.simulation.output:
                logger.warning("No rules activated, using default")
                output = 50
            else:
                output = self.simulation.output['recommendation']
            
            # Determine recommendation level
            if output >= 70:
                recommendation = "bagus"
            elif output >= 30:
                recommendation = "cukup"
            else:
                recommendation = "buruk"
            
            return {
                "recommendation": recommendation,
                "confidence": float(output),
                "status": "success",
                "rules_activated": ["rule1", "rule3"],  # Simplified for demo
                "input_parameters": {
                    "temperature": temperature,
                    "humidity": humidity,
                    "light": light,
                    "rain": rain,
                    "time": time
                }
            }
            
        except ValueError as ve:
            logger.warning(f"Input validation error: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Fuzzy evaluation error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error during fuzzy evaluation")