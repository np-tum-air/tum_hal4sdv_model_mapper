package VehicleDefinitions {

    abstract part def Actuator {
        attribute name : String;
    }

    part def BrakeActuator
        specializes Actuator {

        attribute brakingLevel : Real;
    }

    part def SteeringActuator
        specializes Actuator {

        attribute steeringAngle : Real;
    }

    part def VehicleControl {

        part brakes : BrakeActuator;
        part steering : SteeringActuator;
    }
}
