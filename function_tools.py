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
    

def change_fan_speed(rpm: int):
    """
    Sets the fan speed to the specified RPM value.

    Parameters:
        rpm (int): The target fan speed (RPM).

    Returns:
        bool: True if fan speed was successfully set, False otherwise.
    """
    if rpm < 0:
        return False  # RPM can't be negative

    try:
        st.session_state.fan_speed = rpm
        return True
    except Exception as e:
        print("Fan speed change failed:", e)
        return False