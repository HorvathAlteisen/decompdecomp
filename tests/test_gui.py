"""The GUI's own logic, run in node against a stand-in for the page (tests/gui_polls.js): no browser needed."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
GUI_TIMEOUT_SECONDS = 60


def test_the_game_picker_stays_above_existing_project_cards():
    """Returning users need to see the new game's details without scrolling past their projects."""
    static = Path(__file__).resolve().parent.parent / "src" / "decompnet" / "app" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    home = html.split('<main id="home"', 1)[1].split('</main>', 1)[0]
    assert home.index('class="hero"') < home.index('id="recent"')
    css = (static / "app.css").read_text(encoding="utf-8")
    for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "#recent" in selector or ".hero" in selector:
            assert not re.search(r"(?:^|;)\s*order\s*:", declarations), selector


def test_foreground_progress_covers_delayed_starts_and_clears_on_every_outcome():
    if NODE is None:
        pytest.skip("needs node to run the GUI's scripts")
    subprocess.run([NODE, str(Path(__file__).with_name("gui_progress.js"))], check=True,
                   capture_output=True, text=True, timeout=GUI_TIMEOUT_SECONDS)


def test_saved_project_dialog_preserves_state_and_cancels_pending_requests():
    if NODE is None:
        pytest.skip("needs node to run the GUI's scripts")
    subprocess.run([NODE, str(Path(__file__).with_name("gui_restore.js"))], check=True,
                   capture_output=True, text=True, timeout=GUI_TIMEOUT_SECONDS)


def test_a_removed_compiler_range_can_be_reverted_where_it_was_listed():
    """The Remove button left no way back; the part stays greyed in the list with a Revert that adds the same range,
    compiler and flags again, and says the functions it reopened stay open for agents."""
    if NODE is None:
        pytest.skip("needs node to run the GUI's scripts")
    subprocess.run([NODE, str(Path(__file__).with_name("gui_compiler.js"))], check=True,
                   capture_output=True, text=True, timeout=GUI_TIMEOUT_SECONDS)


def test_launcher_keeps_single_and_multiple_model_modes_for_every_provider():
    if NODE is None:
        pytest.skip("needs node to run the GUI's scripts")
    subprocess.run([NODE, str(Path(__file__).with_name("gui_launcher.js"))], check=True,
                   capture_output=True, text=True, timeout=GUI_TIMEOUT_SECONDS)


def test_a_big_games_map_redraws_what_changed_and_polls_dont_pile_up():
    """A poll that brought one better score redrew all of a big game's map (28,900 cells), and every frame of the
    working functions' pulse copied the whole canvas; the project list's asks piled up behind a slow one, and the live
    poll went on in a minimised window. The compiler answer says a project without a map has none, and not that it
    reads MIPS code only (tests/gui_map.js)."""
    if NODE is None:
        pytest.skip("needs node to run the GUI's scripts")
    subprocess.run([NODE, str(Path(__file__).with_name("gui_map.js"))], check=True,
                   capture_output=True, text=True, timeout=GUI_TIMEOUT_SECONDS)


def test_the_function_view_opens_on_best_and_switches_to_latest_after_a_manual_compile():
    """A DS game's function drawer had no latest/best switch: every fork's function was hidden from it. It shows
    wherever a best attempt differs from the source now, opens on the best (what someone fixing a function builds
    on), and switches to the source now after their own compile (tests/gui_function.js)."""
    if NODE is None:
        pytest.skip("needs node to run the GUI's scripts")
    subprocess.run([NODE, str(Path(__file__).with_name("gui_function.js"))], check=True,
                   capture_output=True, text=True, timeout=GUI_TIMEOUT_SECONDS)


@pytest.fixture(scope="module")
def gui():
    if NODE is None:
        pytest.skip("needs node to run the GUI's scripts")
    from decompnet.consoles import CONSOLES

    env = {**os.environ, "GUI_CONSOLES": json.dumps([c.describe() for c in CONSOLES])}  # (/api/state's)
    out = subprocess.run([NODE, str(Path(__file__).with_name("gui_polls.js"))], capture_output=True, text=True,
                         timeout=GUI_TIMEOUT_SECONDS, check=True, env=env)
    result = json.loads(out.stdout)
    assert result["errors"] == []
    return result


def test_a_project_whose_folder_is_missing_says_so_and_can_be_removed(gui):
    """A project the user deleted from disk used to have no way to its Settings: its home card now says the folder is
    missing and removes its database records (never a folder that isn't there) after a confirmation."""
    missing = gui["checks"]["missingProject"]
    assert 'data-remove-project="gone"' in missing["html"] and "Gone &lt;Game&gt;" in missing["html"]
    assert "folder is missing" in missing["html"]
    assert missing["title"] == "Remove project" and "Gone &lt;Game&gt;" in missing["text"] and "records" in missing["text"]
    assert missing["calls"][0] == ["/api/delete", {"method": "POST", "body": {"slug": "gone"}}]
    assert ["home"] in missing["calls"] and ["nav"] in missing["calls"]
    assert missing["notes"] == ["Project removed from decompdecomp."]


def test_a_game_being_imported_shows_at_once_with_a_spinner(gui):
    """Before, an import showed nothing in the list of projects until it completed. The sidebar and the home page
    show the game from the start of its import, with a spinner and a progress bar, and with no project to open. When
    the job of the import runs, the row and the card open the progress of the import. When the project is in the
    database, they show the project with the spinner and the step of the import. When the import completes, they show the project as all other
    projects. The cards of the home page are drawn again only when an import starts or ends.
    The import requests the list immediately after its job starts."""
    importing = gui["checks"]["importing"]
    for shown in (importing["started"]["nav"].split("</div>")[0], importing["started"]["cards"][0]):
        assert "my &lt;game&gt;.z64" in shown and "spin-dot" in shown and 'class="workbar"' in shown
        assert "href" not in shown
    assert len(importing["started"]["cards"]) == 2 and "spin-dot" not in importing["started"]["cards"][1]
    running = importing["running"]
    assert 'href="#/import/j1"' in running["nav"] and running["cards"][0].startswith("#/import/j1|")
    registered = importing["registered"]
    assert "New Game" in registered["nav"] and "spin-dot" in registered["nav"] and "my &lt;game&gt;" not in registered["nav"]
    assert 'href="#/import/j2"' in registered["nav"] and '<span class="np-step">measuring the project</span>' in registered["nav"]
    assert registered["cards"][0].startswith("#/import/j2|")
    assert "New Game" in registered["cards"][0] and "spin-dot" in registered["cards"][0]
    assert importing["same"] == []
    assert "spin-dot" not in importing["done"]["nav"] and "spin-dot" not in "".join(importing["done"]["cards"])
    assert importing["calls"] == ["/api/import", "/api/projects", "/api/job"]


def test_the_row_of_an_import_has_an_x_that_cancels_it(gui):
    """The row of an import has an X when the import can be cancelled: its job runs (the X has the job), or this page
    sends its game (the X has no job: the upload stops). The row of a job that was cancelled says "cancelling" and
    has no X. `running` is the row as the list draws it."""
    importing = gui["checks"]["importing"]
    job, upload, cancelling, other = importing["xs"]
    assert 'class="np-x"' in job and 'data-cancel="j1"' in job and 'data-title="a &lt;b&gt;"' in job
    assert 'class="np-x"' in upload and 'data-cancel=""' in upload and 'data-title="sent.z64"' in upload
    assert 'data-upload="u1"' in upload  # not the name of the file: two uploads can have the same one
    assert cancelling == "" and other == ""
    # the X of an upload: the request of this page stops, and the server is told (a request that stops after its
    # last byte arrived starts its job all the same)
    assert importing["cancelled"] == {"stopped": 1, "marked": True,
                                      "sent": [["/api/import/cancel", {"upload": "u1"}]]}
    assert 'data-cancel="j1"' in importing["running"]["nav"] and "np-x" not in importing["started"]["nav"]


def test_the_bar_of_an_import_row_does_not_start_again_and_a_row_that_opens_nothing_says_so(gui):
    """Each time the list of projects was drawn again (each 5 s, and at each click on a row), the progress bars of all
    imports started again from the left. A bar that is drawn again continues at the time of the clock. The row of an
    import whose job did not start (its game is copied into the app) is not a link: the pointer over it shows that the row
    opens nothing."""
    static = Path(__file__).parents[1] / "src" / "decompnet" / "app" / "static"
    css, sidebar = (static / "app.css").read_text(encoding="utf-8"), (static / "js" / "sidebar.js").read_text(encoding="utf-8")
    delay = re.fullmatch(r"-(\d+)ms", gui["checks"]["importing"]["started"]["barDelay"])
    assert delay and int(delay[1]) < 2500
    # the times in sidebar.js are those of the animations in app.css
    assert "animation: workbar 1.25s ease-in-out infinite alternate" in css and "WORKBAR_MS = 2500" in sidebar
    assert "animation: spin .8s linear infinite" in css and "SPIN_MS = 800" in sidebar
    assert "div.nav-proj { cursor: not-allowed; }" in css


def test_the_row_of_an_import_shows_its_step_and_opens_its_progress_again(gui):
    """The home page hid the progress of an import each time it opened, and nothing brought it back. The row of an
    import in the sidebar shows the step of the import, and it opens the home page with the progress of that import
    (its step, its log and its time). This is also true for an import that the page did not start. The drop zone
    shows one import at a time: a different import that continues does not write its step or its time into it, and a
    new import takes the drop zone. The page asks for an import one time in each interval, also after its row
    opened it again. When an import completes, its project opens.

    The row of the import that the drop zone shows is the selected row, as the row of an open project is: it had no
    frame. A new import takes the address of the import that was shown, and the address of an import that ended
    becomes the address of the home page: the row of a different import does not stay the selected one."""
    progress = gui["checks"]["importProgress"]
    assert 'href="#/import/j"' in progress["row"] and '<span class="np-step">splitting the game</span>' in progress["row"]
    assert progress["started"]["busy"] and not progress["started"]["idle"]
    assert progress["started"]["step"] == "splitting the game" and progress["started"]["selected"] == []
    assert progress["left"]["idle"] and not progress["left"]["busy"]
    back = progress["back"]
    assert back["busy"] and not back["idle"] and "my-game.z64" in back["title"]
    assert back["step"] == "disassembling every function"
    assert back["log"] == "splitting the game\ndisassembling every function"
    assert back["time"] == " · 1:00" and progress["askedAgain"] == 1 and back["selected"] == ["j"]
    other = progress["other"]
    assert other["busy"] and "other-game.iso" in other["title"]
    assert other["step"] == "reading the disc" and other["log"] == "reading the disc" and other["time"] == ""
    assert other["selected"] == ["k"]
    assert progress["still"] == other
    fresh = progress["fresh"]
    assert fresh["busy"] and fresh["title"] == "Opening Demo Quest 64…" and fresh["step"] == "finding the code segments"
    assert fresh["selected"] == [] and progress["freshAddress"] == "#/"
    # the page opens at the address of an import (a reload): before, the list of projects was not there yet, and the
    # page went to the home page without the import
    reopened = progress["reopened"]
    assert reopened["busy"] and reopened["title"] == "Analysing other-game.iso…" and reopened["selected"] == ["k"]
    assert progress["gone"] == {"address": "#/", "selected": []}
    assert progress["opened"] == "#/p/other-game"


def test_two_imports_at_the_same_time_do_not_write_into_the_progress_of_each_other(gui):
    """With two imports, the drop zone changed between the two: the upload of each game wrote its name and its bar
    into the drop zone, the import whose upload ended first took the drop zone, and the row of an import showed an old
    step and an empty log until the server answered again (seconds, while two imports run). The drop zone shows one
    import, and only that import writes into it. The row of an import shows the step and the log that the page has
    of that import immediately. An import that fails shows why, and the row of the other import shows that import
    again."""
    apart = gui["checks"]["importsApart"]
    for shown in (apart["twoUploads"], apart["firstRuns"]):
        assert shown["busy"] and shown["upload"] and not shown["work"] and shown["bar"] == "25.0%"
        assert shown["title"] == "Copying Game B… into decompdecomp… 25%" and shown["log"] == ""
    both = apart["bothRun"]
    assert both["title"] == "Analysing Game B…" and both["step"] == "unpacking the cartridge"
    assert both["work"] and not both["upload"]
    assert apart["stays"]["step"] == "finding the functions"
    assert apart["rowA"]["title"] == "Analysing a.bin…" and apart["rowA"]["step"] == "splitting the game"
    assert apart["rowA"]["log"] == "reading the disc\nsplitting the game" and apart["rowA"]["work"]
    assert apart["rowB"]["title"] == "Analysing b.nds…" and apart["rowB"]["step"] == "finding the functions"
    assert apart["rowB"]["log"] == "unpacking the cartridge\nfinding the functions"
    failed = apart["failed"]
    assert failed["error"] and not failed["busy"] and failed["name"] == "b.nds" and failed["address"] == "#/"
    again = apart["again"]
    assert again["busy"] and not again["error"] and again["step"] == "splitting the game"


def test_a_ds_rom_is_told_by_its_header_as_the_server_tells_it(gui):
    nds = gui["checks"]["nds"]
    assert nds["good"] == ["nds", "ADQE", "DEMOQUESTDS"]
    assert nds["broken"] is None and "checksum" in nds["said"]
    xbox = gui["checks"]["xbox"]
    assert xbox["good"] == ["xbox", "Xbox program (XBE)"] and xbox["misaligned"] is None
    assert xbox["iso"] == xbox["dump"] == "xbox" and xbox["plain"] is None and "Xbox 360" in xbox["x360"]


def test_a_ps3_program_is_taken_and_its_encrypted_eboot_says_what_to_do(gui):
    ps3 = gui["checks"]["ps3"]
    assert ps3["good"] == ["ps3", "ELF program", 0x13000] and ps3["self"] is None
    assert "SELF" in ps3["said"] and "decrypt your own copy" in ps3["said"] and "EBOOT.ELF" in ps3["said"]


def test_a_gba_rom_is_told_by_its_header_as_the_server_tells_it(gui):
    gba = gui["checks"]["gba"]
    assert gba["good"] == ["gba", "ADQE", "DEMOQUEST"]
    assert gba["broken"] is None and "Game Boy Advance" in gba["said"]


def test_an_effort_goes_only_to_an_agent_that_offers_it(gui):
    assert gui["checks"]["efforts"] == ["opus#xhigh", "deepseek/v4", "m"]


def test_opening_another_project_shows_nothing_from_before(gui):
    """Two games with agents at work: opening the second one flooded it with notifications. The first game's poll,
    slow under load, kept the second one's first poll from running, and its next poll took the last 60 events as
    new. A project's poll toasts nothing now: news is the notification centre's, which starts where the feed was
    when the window opened, so the 60 old matches never show."""
    assert gui["toasts"] == []
    assert len(gui["notes"]) == 2  # only the news below


def test_the_notification_centre_tells_each_projects_news_in_one_line_per_burst(gui):
    """One feed for the whole app: the project's name, the agent and what happened; 14 matches in a row are one line
    that counts up ("+13 more matches"), and another project's paused helper is a line of its own."""
    matches, paused = gui["notes"]
    assert matches.startswith("Ridge Racer V") and "claude-2 matched func_200" in matches and "+13 more matches" in matches
    assert paused.startswith("Demo Quest 64") and "claude-1 paused: the provider is out of credit" in paused
    assert gui["unread"] == 2


def test_fork_and_join_say_what_is_wrong_before_anything_starts(gui):
    """A fork of "hello" reached git, and a join with the link "hello" showed an empty box: the page checks the
    shapes the app accepts first, says what's wrong in a sentence, and keeps the button off until it's right."""
    empty, word, ssh, other_host, github, gitlab = gui["checks"]["repo"]
    assert github == gitlab == ""
    assert "https://github.com/owner/repo" in word and "https address" in ssh and "GitHub, GitLab, Codeberg" in other_host
    assert empty and "Username" not in word
    bad_link, invite, bare_room = gui["checks"]["invite"]
    assert bad_link.startswith("That isn't an invite link") and invite == bare_room == ""
    no_copy, bad_name, ready = gui["checks"]["join"]
    assert "copy of the game" in no_copy and "letters, digits" in bad_name and ready == ""


def test_the_autopilots_run_and_its_summary_are_one_notification(gui):
    """The autopilot's matches and its summary ("20 of 95 functions matched from machine drafts") were two lines saying
    the same thing. The summary ends the run's line; an agent's match after it is a line of its own."""
    run, agent, alone = gui["checks"]["autopilot"]
    assert run == "Autopilot: 2 of 95 functions matched from machine drafts"
    assert agent == "claude-1 matched func_3" and alone.startswith("Autopilot: 0 of 1")


def test_stopped_helpers_claims_do_not_read_as_agents_working(gui):
    """#99: the permuter claims a function for half an hour and its claim outlives the helper and a restart, so the
    header still said "1 agent working" with every helper stopped. The app's own workers (the permuter, the
    autopilot, decompdecomp, and a room host's) aren't agents anyone started; another computer's helper still is."""
    agents = gui["checks"]["agents"]
    assert agents["ownOnly"] == agents["nameless"] == 0
    assert agents["outside"] == 1


def test_a_helper_going_between_waiting_and_working_does_not_reorder_the_rows(gui):
    """#99: with four API helpers on one project the rows jumped every time one went from waiting to working (or
    back), so following one agent with the eye was impossible. Live helpers keep their name order; only starting or
    stopping one moves it, and decompiling helpers still come before polishing ones."""
    agents = gui["checks"]["agents"]
    assert agents["flipped"] == agents["again"] == ["alpha", "beta"]
    assert agents["rows"] == ["working-one", "stopped-one", "polishing", "paused-one"]


def test_searching_functions_looks_at_names_and_addresses_before_the_segment(gui):
    """Searching "ma" listed every function of the segment "main". A ROM's segment counts only when no name or address
    has the text; a fork's source file is shown in the list, so it always counts there."""
    rom_ma, fork_main, _, nothing = gui["checks"]["search"]
    assert rom_ma == ["main_loop"]
    assert fork_main == ["func_80000400", "lerp", "main_loop"] and nothing == []


def test_the_project_can_choose_which_functions_helpers_take_first(gui):
    """#205: the owner's order is a select beside the instructions, saved to the project; a refused save puts the
    server's value back instead of leaving the page showing an order that isn't in force."""
    static = Path(__file__).resolve().parent.parent / "src" / "decompnet" / "app" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    for value, label in [("", "Default"), ("easiest", "Smallest first"), ("hardest", "Largest first"),
                         ("closest", "Closest to matching first"), ("untried", "Not yet tried first")]:
        assert f'<option value="{value}">{label}' in html, value
    order = gui["checks"]["claimOrder"]
    assert order["saved"] == {"url": "/api/claim-order", "body": {"slug": "a", "order": "untried"},
                              "value": "untried"}
    assert order["reverted"] == "untried" and "nobody has tried yet" in order["text"]
    assert any("read-only" in note for note in order["notes"])


def test_the_theme_button_goes_round_system_light_and_dark(gui):
    """The sidebar's button only flipped light and dark: once pressed, the system's choice was gone for good."""
    assert gui["checks"]["themes"] == ["light", "dark", ""]
    assert gui["checks"]["systemThemes"] == ["", "light", "dark", ""]


def test_model_advice_is_dismissed_by_model_for_a_day_and_stays_hidden_as_its_counts_move(gui):
    """#131: the advice box came back on every poll, with every model's paragraph, and pushed the helpers off the
    screen. Its close button remembers the models it dismissed for that project: their advice stays away while its
    live counts change, another model's advice still shows, another project has its own dismissals, and after a day
    the advice may show again."""
    advice = gui["checks"]["advice"]
    assert advice["shown"]["hidden"] is False and "100 compiles" in advice["shown"]["text"]
    assert advice["dismissed"]["hidden"] is True
    assert list(advice["dismissed"]["stored"]) == ["model-a"]
    assert isinstance(advice["dismissed"]["stored"]["model-a"], (int, float))
    assert advice["sameModel"] == {"hidden": True, "text": ""}
    assert advice["otherProject"]["hidden"] is False and "900 compiles" in advice["otherProject"]["text"]
    assert advice["otherModel"]["hidden"] is False and "stronger model" in advice["otherModel"]["text"]
    assert advice["expired"]["hidden"] is False and "900 compiles" in advice["expired"]["text"]


def test_an_unknown_compiler_says_the_project_was_made_with_another_tool(gui):
    """#118: a project from another tool names a compiler decompdecomp doesn't have. The banner called it a compiler
    with no build for this computer; it says what it is and where to pick one decompdecomp has."""
    said = gui["checks"]["unknownCompiler"]
    assert said["hidden"] is False and said["className"] == "notice bad"
    assert "msvcxx-x86_64 isn't a compiler decompdecomp has" in said["text"] and "another tool" in said["text"]
    assert "Settings" in said["text"] and "no build for this computer" not in said["text"]


def test_the_drop_zone_takes_playstation_programs_and_leaves_a_discs_console_to_its_system_cnf(gui):
    """A PS-X EXE is the PS1's; a disc image could be any PlayStation's until the server reads it."""
    assert gui["checks"]["dropped"] == ["ps", "playstation", "PlayStation 1, 2 or PSP", None]


def test_the_drop_zone_tells_psp_games_from_the_ps2s_and_says_what_to_do_with_what_it_cant_read(gui):
    """A PSP's UMD image starts like a PS2 disc and its programs are MIPS ELFs like the PS2's, and a .cso starts with
    CISO like a compressed GameCube disc: the drop zone reads further, so a PSP game isn't taken for another
    console's. A .cso is a PlayStation disc whose console the server reads inside it; a .zso or an EBOOT.PBP (not
    readable yet) says what to drop instead."""
    psp = gui["checks"]["psp"]
    # a UMD image, a PS2 disc, a GameCube CISO, a .cso, a PRX module, an Allegrex program, a PS2 program
    assert psp["platforms"] == ["psp", "playstation", "gcwii", "playstation", "psp", "psp", "ps2"]
    assert psp["cso"] == "CSO disc image"
    zso, pbp = psp["said"]
    assert "ZSO" in zso and "decompress it to .iso" in zso
    assert "EBOOT.PBP" in pbp and "encrypted" in pbp and ".iso" in pbp
    assert psp["name"] == "PlayStation 1, 2 or PSP"


def test_the_drop_zone_takes_64_bit_programs_and_tells_arm_and_dos_ones_apart(gui):
    """It said "a 64-bit or non-x86 Windows program (or a DOS one)" for all three: it says which, before uploading
    hundreds of megabytes the import would refuse. 64-bit games start now: a 64-bit program is the PC console's,
    its entry above 4 GB shown whole, offered the pack of 2017's 64-bit compiler (the server's pack_x64)."""
    x64, arm, x86, dos, damaged = gui["checks"]["windows"]
    assert x64[0] == "win32" and x64[2] == ["64-bit Windows program (.exe)", "0x140001000", "msvc2015", "msvc2015",
                                                "x64"]
    assert arm[0] is None and "ARM" in arm[1] and "32-bit or 64-bit x86" in arm[1]
    assert x86[0] == "win32"  # a 32-bit x86 one is the PC console's (notSupported is asked only otherwise)
    assert dos[0] is None and "DOS program" in dos[1]
    assert damaged[0] is None and "header is damaged" in damaged[1]


def test_each_computer_in_a_room_has_one_colour_on_every_screen(gui):
    """In a room, every agent's name had the same look whoever ran it. Each computer has a colour now, the same on
    the host's screen and every guest's: the host's first, then the members in the order they joined."""
    c = gui["checks"]["computers"]
    # the host's, alex's, kim's own (kim's screen), the autopilot (none), the host's with a dot in its model's name
    assert c["guest"] == [0, 1, 2, None, 0]
    assert c["host"] == [0, 1, 2, 0]  # the same colours on the host's screen
    assert c["alone"] is None  # no room, no colours


def test_polish_is_offered_once_half_the_games_own_code_matches(gui):
    """An Xbox game had all 33 of its own functions matched and no Polish to choose: the launcher weighed them against
    all 274, its 241 set-aside ones (library code, assembly) included, which the header leaves out."""
    assert gui["checks"]["polish"] == [True, False, False, False]


def test_the_import_offers_every_compiler_of_the_games_console(gui):
    """The import's compiler test can only try what's installed: a game linked by CodeWarrior was guessed right only
    because its GCC was there. The import offers the console's missing compilers, every PlayStation's for a disc."""
    assert gui["checks"]["missing"] == [["ee-gcc-2.96", "mwcps2-3.0.1"], 3, 0]


def test_a_dropped_pc_game_is_offered_the_visual_cpp_pack_its_program_names(gui):
    """A game of 2005-2010 was offered the 6.0-7.1 pack, and its import then asked for 2005-2010's: the drop reads the
    Rich header (or the linker's version) as the import does, and offers the pack the import will build with."""
    from decompnet.consoles.pc import scratch

    packs = gui["checks"]["pcPack"]
    for head, pack, offered, target in packs:
        built = scratch.describe(bytes.fromhex(head))
        assert pack == offered == scratch.compiler_pack(built.pack_version), (head, built)
        assert target == "x86"  # (a 32-bit program: its import lists 32-bit compilers only, next)
    assert [p for _, p, _, _ in packs] == ["msvc2005", "msvc", "msvc", "msvc2005", "msvc2005", "msvc",
                                        "msvc2015", "msvc2015", "msvc2005", "msvc2015", "msvc2015"]


def test_a_pc_game_dropped_before_the_page_loaded_is_offered_its_pack_and_32_bit_compilers(gui):
    """Review of #138: the drop read a program before the page's state arrived, whose PC table names the pack (pcPack),
    so a 2017 game dropped early was offered 6.0-7.1's; and the import's dialog listed MSVC/14.16-x64 for a 32-bit
    program, which can never match it. Run through the page's own pickFile and setupCompilers."""
    drop = gui["checks"]["pcDrop"]
    assert drop["pack"] == "msvc2015"
    assert "MSVC/6.0" in drop["options"] and "MSVC/14.16" in drop["options"], drop
    assert not any(option.endswith("-x64") for option in drop["options"]), drop


def test_the_drop_zone_knows_the_visual_cpp_ids_the_import_knows():
    """home.js reads a dropped program's Rich header for the pack to offer (pcPack): its ids are scratch's."""
    from decompnet.consoles.pc import scratch

    text = (Path(__file__).resolve().parent.parent / "src" / "decompnet" / "app" / "static" / "js" / "home.js").read_text()
    table = re.search(r"const RICH_COMPILERS = \{(.*?)\};", text, re.S).group(1)
    js = {v: {i for lo, hi in re.findall(r"\[(0x[0-9a-f]+), (0x[0-9a-f]+)\]", ranges) for i in range(int(lo, 16),
                                                                                                    int(hi, 16))}
          for v, ranges in re.findall(r'"([\d.]+)": (\[\[.*?\]\])', table)}
    assert js == {v: {*compilers, *glued} for v, compilers, glued in scratch.RICH_COMPILERS}
    linkers = re.search(r"const RICH_LINKERS = \[(.*?)\];", text, re.S).group(1)
    assert {int(x, 16) for x in re.findall(r"0x[0-9a-f]+", linkers)} == scratch.RICH_LINKERS


def test_linux_vm_setup_shows_readiness_and_uses_progress():
    if NODE is None:
        pytest.skip('needs node to run GUI scripts')
    subprocess.run([NODE, str(Path(__file__).with_name('gui_linuxvm.js'))], check=True,
                   capture_output=True, text=True, encoding='utf-8', timeout=GUI_TIMEOUT_SECONDS)

def test_ps4_decrypted_executables_are_accepted_but_other_elfs_are_not(gui):
    assert gui["checks"]["ps4"] == ["ps4", "ps4", None, None]


def test_a_ps4_drop_never_requests_codewarrior_and_explains_host_restrictions(gui):
    for drop in gui["checks"]["ps4Drop"]["drops"]:
        assert drop["pack"] == "" and not drop["consent"] and not drop["disabled"]
        assert "free" in drop["note"] and "Clang 5.0.2" in drop["note"]
        assert drop["extras"] == ["game.functions.jsonl"]
    unsupported = gui["checks"]["ps4Drop"]["unsupported"]
    assert unsupported["disabled"] and not unsupported["consent"] and "WSL 2" in unsupported["note"]
