from collections import OrderedDict
from copy import deepcopy
from typing import List, Dict

from serial import Keyboard, Key, serialize, sort_keys
from util import min_x_y


def extract_ml_val_ndx(key, ml_val_lbl_ndx=3, ml_ndx_lbl_ndx=5):
    val_lbl = key.labels[ml_val_lbl_ndx]
    ndx_lbl = key.labels[ml_ndx_lbl_ndx]

    if not (val_lbl.isnumeric() and ndx_lbl.isnumeric()):
        if val_lbl.isnumeric():
            raise Exception(f"Key at ({key.x}, {key.y}) has a multilayout value of {val_lbl}, but is missing a valid multilayout index.")
        elif ndx_lbl.isnumeric():
            raise Exception(f"Key at ({key.x}, {key.y}) has a multilayout index of {ndx_lbl}, but is missing a valid multilayout value.")
        else:
            raise Exception(f"Key at ({key.x}, {key.y}) is missing a valid multilayout value abd index label.")

    val = int(val_lbl)
    ndx = int(ndx_lbl)
    return val, ndx


def extract_row_col(key, row_lbl_ndx=9, col_lbl_ndx=11):
    row_lbl = key.labels[row_lbl_ndx]
    col_lbl = key.labels[col_lbl_ndx]

    # Error keys without row and/or column labels
    # # if not (row_lbl and col_lbl): # this line is needed in the case that labels are None (no longer required since I changed the default label values to empty strings instead)
    # #     continue
    if not (row_lbl.isnumeric() and col_lbl.isnumeric()):
        if row_lbl.isnumeric():
            raise Exception(f"Key at ({key.x}, {key.y}) has a row value of {row_lbl}, but is missing a valid column label.")
        elif col_lbl.isnumeric():
            raise Exception(f"Key at ({key.x}, {key.y}) has a column value of {col_lbl}, but is missing a valid row label.")
        else:
            raise Exception(f"Key at ({key.x}, {key.y}) is missing a valid row and/or column label.")

    row = int(row_lbl)
    col = int(col_lbl)
    return row, col


def get_multilayout_keys(kbd: Keyboard) -> bool:
    """Returns a list of multilayout keys"""
    keys = []
    for key in kbd.keys:
        if key.labels[3] or key.labels[5]:
            extract_ml_val_ndx(key)  # Just to test labels
            keys.append(key)
    return keys


def get_alternate_layouts(kbd: Keyboard, layout_info: Dict[str, List[int]]) -> Dict[str, List[Key]]:
    """
    Returns a dict mapping a layout name to a list of keys
    Takes in a keyboard and a dict that maps names to a list of option indices
    """
    alt_layouts = {}
    for name, choices in layout_info.items():
        resulting_keys = get_specific_layout(kbd, choices)
        alt_layouts[name] = resulting_keys
    return alt_layouts


def get_specific_layout(kbd: Keyboard, layout_idx: List[int]) -> List[Key]:
    """Returns a Keyboard with the specified multilayout
    The layout_idx list should specify the index of each specified layout option
    Based on the configured input keyboard
    """
    ml_keys = get_multilayout_keys(kbd)

    # We will return these keys for this layout
    qmk_keys = []
    # Add non-multilayout keys to the list for now
    for key in [k for k in kbd.keys if k not in ml_keys]:
        # Ignore VIAL Encoder keys
        if key.labels[4] == 'e':
            continue
        qmk_keys.append(key)

    # Generate a dict of all multilayouts
    ml_dict = {}
    for key in [k for k in kbd.keys if k in ml_keys]:
        # Ignore VIAL Encoder keys
        if key.labels[4] == 'e':
            continue

        ml_ndx, ml_val = extract_ml_val_ndx(key)

        # Create dict with multilayout index if it doesn't exist
        if not ml_dict.get(ml_ndx):
            ml_dict[ml_ndx] = {}

        # Create dict with multilayout value if it doesn't exist
        # Also create list of keys if it doesn't exist
        if not ml_dict[ml_ndx].get(ml_val):
            ml_dict[ml_ndx][ml_val] = []

        # Add key to dict if not in already
        if not key in ml_dict[ml_ndx][ml_val]:
            ml_dict[ml_ndx][ml_val].append(key)

    # Validate that our layout idx list is properly formed
    if len(layout_idx) != len(ml_dict.keys()):
        raise Exception(f"Layout index list does not have the proper number of options selected")

    # Validate that each selected index for each option exists
    for option_idx, selected_idx in enumerate(layout_idx):
        if selected_idx >= len(ml_dict[option_idx]):
            raise Exception(f"Selected index {selected_idx} does not exist for option index {option_idx}")

    # Add each selected key to the layout
    for option_idx, selected_idx in enumerate(layout_idx):
        selected_keys = ml_dict[option_idx][selected_idx]
        for selected_key in selected_keys:
            if selected_idx > 0:
                # Add an offsets dict if it doesn't exist
                if not ml_dict[option_idx].get("offsets"):
                    ml_dict[option_idx]["offsets"] = {}

                # Calculate the appropriate offset for this ml_val if it hasn't been calculated yet
                if not ml_dict[option_idx]["offsets"].get(selected_idx):
                    # Calculate and set x and y offsets
                    xmin, ymin = min_x_y(ml_dict[option_idx][0])
                    x, y = min_x_y(ml_dict[option_idx][selected_idx])

                    ml_x_offset = xmin - x
                    ml_y_offset = ymin - y

                    ml_dict[option_idx]["offsets"][selected_idx] = (ml_x_offset, ml_y_offset)
                else:
                    # Get the offset from ml_dict
                    ml_x_offset, ml_y_offset = ml_dict[option_idx]["offsets"][selected_idx]

                # Offset the x and y values
                selected_key.x += ml_x_offset
                selected_key.y += ml_y_offset

                # For rotated keys only
                if selected_key.rotation_angle:
                    selected_key.rotation_x -= ml_x_offset
                    selected_key.rotation_y -= ml_y_offset

            # Add the key to the final list
            qmk_keys.append(selected_key)
    # Offset all the remaining keys (align against the top left)
    x_offset, y_offset = min_x_y(qmk_keys)
    for key in qmk_keys:
        key.x -= x_offset
        key.y -= y_offset

    sort_keys(qmk_keys)  # sort keys (some multilayout keys may not be in the right order)

    return qmk_keys



def get_layout_all(kbd: Keyboard) -> Keyboard:
    """Returns a Keyboard with all maximum multilayouts chosen.
    For each multilayout, choose the layout option with the most amount of keys.
    For any one multilayout, if all layout options have the same number of keys,
    the 0th option will be defaulted to. Used for things like the info.json."""
    kbd = deepcopy(kbd)
    ml_keys = get_multilayout_keys(kbd)

    # This list will replace kbd.keys later
    # It is a list with only the keys to be included in the info.json
    qmk_keys = []
    # Add non-multilayout keys to the list for now
    for key in [k for k in kbd.keys if k not in ml_keys]:
        # Ignore VIAL Encoder keys
        if key.labels[4] == 'e':
            continue
        qmk_keys.append(key)

    # Generate a dict of all multilayouts
    # E.g. Used to test and figure out the multilayout value with the maximum amount of keys
    ml_dict = {}
    for key in [k for k in kbd.keys if k in ml_keys]:
        # Ignore VIAL Encoder keys
        if key.labels[4] == 'e':
            continue

        ml_ndx, ml_val = extract_ml_val_ndx(key)

        # Create dict with multilayout index if it doesn't exist
        if not ml_dict.get(ml_ndx):
            ml_dict[ml_ndx] = {}

        # Create dict with multilayout value if it doesn't exist
        # Also create list of keys if it doesn't exist
        if not ml_dict[ml_ndx].get(ml_val):
            ml_dict[ml_ndx][ml_val] = []

        # Add key to dict if not in already
        if not key in ml_dict[ml_ndx][ml_val]:
            ml_dict[ml_ndx][ml_val].append(key)

    # Iterate over multilayout keys
    for key in [k for k in kbd.keys if k in ml_keys]:
        ml_ndx, ml_val = extract_ml_val_ndx(key)

        # Get current list of amount of keys in all ml options
        ml_val_length_list = [len(ml_dict[ml_ndx][i]) for i in ml_dict[ml_ndx].keys() if isinstance(i, int)]

        max_val_len = max(ml_val_length_list)  # Maximum amount of keys over all ml_val options
        current_val_len = len(ml_dict[ml_ndx][ml_val])  # Amount of keys for current ml_val

        # Whether or not the current ml_val is the max layout
        current_is_max = max_val_len == current_val_len

        # If all multilayout values/options have the same amount of keys
        all_same_length = len(set(ml_val_length_list)) == 1

        # If the current multilayout value/option is the max one
        if not ml_dict[ml_ndx].get("max"):
            if all_same_length:
                ml_dict[ml_ndx]["max"] = 0  # Use the default/0th option
            elif current_is_max:
                ml_dict[ml_ndx]["max"] = ml_val  # Set the max to current ml_val
            else:
                continue

        # Skip if not the max layout value/option
        # (can't use current_is_max because of cases where options have the same amount of keys)
        if not ml_dict[ml_ndx]["max"] == ml_val:
            continue

        # OFFSET MULTILAYOUT KEYS APPROPRIATELY #

        # If the current multilayout value/option isn't default/the 0th layout option
        # (keys will already be in place)
        if ml_val > 0:
            # Add an offsets dict if it doesn't exist
            if not ml_dict[ml_ndx].get("offsets"):
                ml_dict[ml_ndx]["offsets"] = {}

            # Calculate the appropriate offset for this ml_val if it hasn't been calculated yet
            if not ml_dict[ml_ndx]["offsets"].get(ml_val):
                # Calculate and set x and y offsets
                xmin, ymin = min_x_y(ml_dict[ml_ndx][0])
                x, y = min_x_y(ml_dict[ml_ndx][ml_val])

                ml_x_offset = xmin - x
                ml_y_offset = ymin - y

                ml_dict[ml_ndx]["offsets"][ml_val] = (ml_x_offset, ml_y_offset)
            else:
                # Get the offset from ml_dict
                ml_x_offset, ml_y_offset = ml_dict[ml_ndx]["offsets"][ml_val]

            # Offset the x and y values
            key.x += ml_x_offset
            key.y += ml_y_offset

            # For rotated keys only
            if key.rotation_angle:
                key.rotation_x -= ml_x_offset
                key.rotation_y -= ml_y_offset

        # Add the key to the final list
        qmk_keys.append(key)

    # Special case to handle when a key isn't in the max multilayout but is required for a separate multilayout
    # E.g. Multilayout where a split spacebar layout doesn't include the original matrix value for full spacebar,
    # since that split multilayout will have more keys and will be picked by default.
    for key in [k for k in kbd.keys if k in ml_keys]:
        ml_ndx, ml_val = extract_ml_val_ndx(key)
        max_val = ml_dict[ml_ndx]['max']
        matrix_list = [(extract_row_col(key)) for key in ml_dict[ml_ndx][max_val]]
        if (extract_row_col(key)) not in matrix_list:
            # print(key)
            ml_dict[ml_ndx][max_val].append(key)
            # Temporary, currently just adds the first key it sees into the layout_all, may cause issues but is a niche scenario
            qmk_keys.append(key)

    # Offset all the remaining keys (align against the top left)
    x_offset, y_offset = min_x_y(qmk_keys)
    for key in qmk_keys:
        key.x -= x_offset
        key.y -= y_offset

    # Override kbd.keys with the keys only to be included in the info.json
    kbd.keys = qmk_keys
    sort_keys(kbd.keys)  # sort keys (some multilayout keys may not be in the right order)

    # DEBUG: To view what the layout_all will look like (as a KLE)
    import json
    from util import write_file
    test_path = 'test.json'
    write_file(test_path, json.dumps(serialize(kbd), ensure_ascii=False, indent=2))

    return kbd


def convert_key_list_to_layout(keys: List[Key]) -> List:
    """Creates a layout array given a list of keys"""
    qmk_layout = []
    for key in keys:
        # Ignore ghost keys (e.g. blockers)
        if key.decal:
            continue

        # Initialize a key (dict)
        qmk_key = OrderedDict(
            label="",
            x=int(key.x) if int(key.x) == key.x else key.x,
            y=int(key.y) if int(key.y) == key.y else key.y,
        )

        if key.width != 1:
            qmk_key['w'] = key.width
        if key.height != 1:
            qmk_key['h'] = key.height

        if key.labels[9].isnumeric() and key.labels[11].isnumeric():
            row, col = extract_row_col(key)
            qmk_key['matrix'] = [int(row), int(col)]

        if key.labels[0]:
            qmk_key['label'] = key.labels[0]
        else:
            del (qmk_key['label'])

        qmk_layout.append(qmk_key)
    return qmk_layout
