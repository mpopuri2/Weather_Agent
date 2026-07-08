import os

def save_file(text: str):
    filename: str = "output.txt"
    folder: str = "output"
    # Step 1: Check folder — create if missing
    if not os.path.exists(folder):
        os.makedirs(folder)
        folder_status = f"Folder '{folder}' did not exist, created it."
    else:
        folder_status = f"Folder '{folder}' already exists."

    # Step 2: Build full path
    filepath = os.path.join(folder, filename)

    # Step 3: Check file — if it exists, generate a new name instead of overwriting
    if os.path.exists(filepath):
        name, ext = os.path.splitext(filename)
        counter = 1
        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_filepath = os.path.join(folder, new_filename)
            if not os.path.exists(new_filepath):
                filepath = new_filepath
                break
            counter += 1
        file_status = f"File already existed, saved as new file: {filepath}"
    else:
        file_status = f"File did not exist, created: {filepath}"

    # Step 4: Write
    with open(filepath, "w") as f:
        f.write(text)

    return f"{folder_status} {file_status}"


# def save_file(text):
#     with open("../outputs/output.txt","w") as f:
#         f.write(text)

