# stardew-host-swap

English | [中文](README.md)

A Python tool for **swapping the host and client player identities in Stardew Valley 1.6 multiplayer saves**.

The current project implements:
Swapping a selected farmhand character with the host character in a multiplayer save, while preserving as much player data, save preview information, and key ownership relationships as possible.

## License

This project is released under the **MIT License**.

---

## Overview

In Stardew Valley multiplayer saves:

- The host player is located under the `SaveGame/player` node
- Farmhand players are located under the `SaveGame/farmhands/Farmer` nodes

From the save structure perspective, although both host and farmhands are of type `Farmer`, they are **not** interchangeable by simply renaming or moving nodes.
After a direct swap, you will often run into issues such as:

- Inconsistent `SaveGameInfo` preview data
- Progress loss caused by `mailReceived`
- Missing multiplayer character selection entries due to incorrect `homeLocation`
- `userID` binding issues
- Unsynchronized ownership references such as `farmhandReference`

This project was written to address those problems.

---

## Current Features

The current version supports:

- Swapping the `player` in the main save with a specified `farmhands/Farmer`
- Synchronizing and fixing `SaveGameInfo`
- Fixing `mailReceived`
- Fixing `homeLocation`
- Fixing `userID`
- Fixing part of the ownership fields based on `UniqueMultiplayerID`:
  - `farmhandReference`
- Supporting **pre-check / report mode**
- Supporting direct input of the **save folder path**
- Supporting **in-place modification of the original save files**
- Automatically creating `_bak` backup files

---

## Usage

### 1. Requirements

You need:

- Python 3.10 or higher
- A Stardew Valley multiplayer save folder. On Windows, it is usually located under `%appdata%\StardewValley\Saves`

A typical save directory looks like this:

```text
name_123456789/
  name_123456789
  SaveGameInfo
```

Where:

- Folder name: `name_123456789`
- Main save file: `name_123456789`
- Preview info file: `SaveGameInfo`

### 2. List the host and all farmhand characters in the save

```bash
python main.py "\path\to\name_123456789" --list
```

### 3. Run a pre-check first (recommended)

Select by character name (`NAME` is the farmhand player name that you want to swap with the current host):

```bash
python main.py "\path\to\name_123456789" --target-name NAME --report
```

Or select by `UniqueMultiplayerID` (`ID` is the farmhand player ID that you want to swap with the current host):

```bash
python main.py "\path\to\name_123456789" --target-id ID --report
```

This will output the planned swap results, but will not modify any actual files.

### 4. Perform the actual swap

```bash
python main.py "\path\to\name_123456789" --target-name NAME
```

After running the command, the tool will:

- Back up the original main save as `original_filename_bak`
- Back up `SaveGameInfo` as `SaveGameInfo_bak`
- Swap the data of the farmhand player `NAME` with the current host player
- Write the modified content back to the original save files

---

## Processing Logic

The current processing flow is roughly:

1. Read the main save XML and locate:
   - `SaveGame/player`
   - The target `SaveGame/farmhands/Farmer`

2. Use an **original XML text-level** approach to swap:
   - The internal content of the `player` node
   - The internal content of the specified `Farmer` node

3. After the swap, apply targeted fixes to:
   - `mailReceived`
   - `homeLocation`
   - `userID`

4. Synchronize some ownership references:
   - `farmhandReference`

5. Write the swapped `player` content into `SaveGameInfo/Farmer`

6. Automatically back up the original files as `_bak` before writing changes

---

## Technical Details

<details>
<summary>Click to expand</summary>

### 1. Main player data swap strategy

The core swap does not rebuild the entire XML tree. Instead, it:

- Locates the inner range of `<player>...</player>`
- Locates the inner range of the target `<Farmer>...</Farmer>`
- Directly swaps these two internal XML fragments

### 2. How `SaveGameInfo` is synchronized

The root node of `SaveGameInfo` is `Farmer`, and it usually includes:

- `xmlns:xsi`
- `xmlns:xsd`

The current implementation does not replace the root tag or modify those namespace declarations.
It only overwrites the inner content of `SaveGameInfo/Farmer` with the swapped `player` inner content from the main save.

### 3. `mailReceived` handling strategy

The current strategy is **host progress first**:

- New host: `original farmhand mailReceived ∪ original host mailReceived`
- New farmhand: keep the original host's `mailReceived`

This is because the host's `mailReceived` often contains global progress flags, and this approach tries to avoid losing them after the host switch.

### 4. `homeLocation` handling strategy

Testing shows that if the swapped host still keeps:

```xml
<homeLocation>FarmHouse</homeLocation>
```

then that character may not appear in the multiplayer character selection list.

So the current fix rules are:

- New host: `homeLocation = FarmHouse`
- New farmhand: `homeLocation = the original cabin location of the target farmhand before the swap`

### 5. `userID` handling strategy

The current implementation uses **position semantics**:

- New host: `userID = empty`
- New farmhand: restore the target farmhand's original `userID` from before the swap

### 6. How `farmhandReference` is handled

The current version performs a two-way ID replacement for the following tag:

- `farmhandReference`

Each matched tag value is checked individually:

- If the original value is the old host ID → replace it with the old farmhand ID
- If the original value is the old farmhand ID → replace it with the old host ID

### 7. Write-back strategy

- First back up the main save as `original_filename_bak`
- If `SaveGameInfo` exists, back it up as `SaveGameInfo_bak`
- Then write the modified content back to the original file names

This makes it easy to roll back using the backup files if testing fails.

</details>

---

## Notes

### 1. The tool creates backups automatically, but manual backup of the whole save folder is still recommended

The current version automatically creates `_bak` files, but for important saves, manually backing up the entire save folder is still strongly recommended.

### 2. This is an experimental tool

It has only been tested repeatedly on version 1.6.15. This project is better suited as:

- A personal-use tool
- An experimental tool for vanilla or lightly modded environments

If your save uses a large number of mods, there may still be issues such as:

- Custom fields not being synchronized
- Additional world/player bindings not being covered

### 3. Not every issue is fully solved

The current tool mainly focuses on:

- Swapping the main character data
- Character visibility
- Basic progress synchronization
- Part of the ownership relationships

It does not yet cover every multiplayer or mod-related edge case.

---

## Known Limitations

- Not all possible `UniqueMultiplayerID` reference fields are handled systematically yet
- Mod-specific custom nodes are not specially supported yet
- Interior furniture and layout of the main house / cabins are not migrated yet
- Compatibility layers for all game version differences are not implemented yet

---

## Recommended Workflow

Recommended order of use:

1. Run `--list` first
2. Then run `--report`
3. Confirm the target character, ID, and expected modifications
4. Then perform the actual swap
5. Test in game:
   - Whether the save loads normally
   - Whether the host character is correct
   - Whether the original host appears in the multiplayer character list
   - Whether houses and ownership behave as expected
6. If something goes wrong, roll back manually using the `_bak` files

---

## Disclaimer

This project is an unofficial tool.
Please back up your save files before use.
Any risks caused by save corruption, character issues, multiplayer problems, or mod compatibility issues are the user's responsibility.

---

## Development Note

AI-assisted tools were used during development.
AI was involved in parts of the code generation, refactoring, troubleshooting, and documentation writing.

To ensure usability, all actual functionality was manually tested and verified before release.
