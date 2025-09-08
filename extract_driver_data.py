# extract_driver_data.py
import pandas as pd

def extract_driver_data(input_csv: str, driver_id: int, output_csv: str):
    """
    Extracts trip data for a specific driver from the dataset and saves it to a new CSV.

    Parameters:
    -----------
    input_csv : str
        Path to the full trip dataset CSV.
    driver_id : int
        The driver ID to filter on.
    output_csv : str
        Path where the filtered dataset will be saved.
    """
    # Load the dataset
    df = pd.read_csv(input_csv)

    # Filter data for the given driver_id
    driver_data = df[df["driver_id"] == driver_id]

    if driver_data.empty:
        print(f"No data found for driver_id {driver_id}.")
    else:
        # Save to a new CSV file
        driver_data.to_csv(output_csv, index=False)
        print(f"Saved {len(driver_data)} records for driver {driver_id} to {output_csv}")


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    input_file = "trip_recommendation_service_dataset.csv"   # path to full dataset
    driver_id_to_extract = 9                                # change to whichever driver you want
    output_file = f"driver{driver_id_to_extract}_trip_data.csv"

    extract_driver_data(input_file, driver_id_to_extract, output_file)
