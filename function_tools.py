import streamlit as st


def change_temperature(delta: int):
    """
    Adjusts the current temperature in the Streamlit session state.

    Args:
        delta (int): The amount to change the temperature by.
                    Positive increases the temperature,
                    negative decreases it.

    Returns:
        bool: True if the change was successful, False otherwise.
    """
    if "temperature" not in st.session_state:
        return False

    try:
        st.session_state.temperature += delta
        return True
    except Exception as e:
        print("Error changing temperature:", e)
        return False
    


def change_fan_speed(delta: int):
    """
    Adjusts the current fan speed in the Streamlit session state.

    Parameters:
        delta (int): The amount to change the fan speed by (can be positive or negative).

    Returns:
        bool: True if the adjustment succeeded, False otherwise.
    """
    if "fan_speed" not in st.session_state:
        return False

    try:
        st.session_state.fan_speed += delta
        return True
    except Exception as e:
        print("Error changing temperature:", e)
        return False


def change_steering_wheel_heating(state: str) -> bool:
    """
    Change the state of the steering wheel heating.

    Args:
        state (str): "On" or "Off"

    Returns:
        bool: True if successful, False otherwise
    """
    import streamlit as st

    if state not in {"On", "Off"}:
        return False

    try:
        st.session_state.steering_wheel_heating = state
        return True
    except Exception as e:
        print("Error changing steering wheel heating:", e)
        return False
