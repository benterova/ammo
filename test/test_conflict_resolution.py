#!/usr/bin/env python3
import os
from pathlib import Path
from common import AmmoController

import pytest

MOD_1 = "conflict_1"
MOD_2 = "conflict_2"

FILES = [
    Path("Data/textures/mock_texture.nif"),
    Path("Data/mock_plugin.esp"),
    Path("file.dll"),
]


def test_duplicate_plugin():
    """
    Test that installing two mods with the same plugin
    doesn't show more than one plugin in the plugins list.
    """
    with AmmoController() as controller:
        # Install both mods
        for mod in [MOD_1, MOD_2]:
            mod_index_download = [i.name for i in controller.downloads].index(
                mod + ".7z"
            )
            controller.install(mod_index_download)

            mod_index = [i.name for i in controller.mods].index(mod)

            controller.activate("mod", mod_index)
            # Ensure there is only one esp
            assert len(controller.plugins) == 1
            controller.commit()
            assert len(controller.plugins) == 1


@pytest.mark.parametrize("use_symlinks", [True, False])
def test_conflict_resolution(use_symlinks):
    """
    Install two mods with the same files. Verify the symlinks
    point back to the mod last in the load order.

    Conflicts for all files and plugins are won by a single mod.
    """
    with AmmoController(use_symlinks) as controller:
        # Install both mods
        for mod in [MOD_1, MOD_2]:
            mod_index_download = [i.name for i in controller.downloads].index(
                mod + ".7z"
            )
            controller.install(mod_index_download)

            mod_index = [i.name for i in controller.mods].index(mod)

            controller.activate("mod", mod_index)
            controller.commit()

        # Activate the plugin
        controller.activate("plugin", 0)

        # Commit changes
        controller.commit()

        # Track our expected mod files to confirm they're different later.
        uniques = []

        def check_links(expected_game_file, expected_mod_file):
            if expected_game_file.is_symlink():
                # Symlink
                assert expected_game_file.readlink() == expected_mod_file
            else:
                # Hardlink
                expected_stat = os.stat(expected_game_file)
                actual_stat = os.stat(expected_mod_file)
                assert expected_stat.st_ino == actual_stat.st_ino

        # Assert that the symlinks point to MOD_2.
        # Since it was installed last, it will be last
        # in both mods/plugins load order.
        for file in FILES:
            expected_game_file = controller.game.directory / file
            expected_mod_file = controller.mods[1].location / file
            uniques.append(expected_mod_file)
            check_links(expected_game_file, expected_mod_file)

        # Rearrange the mods
        controller.move("mod", 1, 0)
        controller.commit()

        # Assert that the symlinks point to MOD_1 now.
        for file in FILES:
            expected_game_file = controller.game.directory / file
            expected_mod_file = controller.mods[1].location / file

            # Check that a different mod is the conflict winner now.
            assert expected_mod_file not in uniques
            check_links(expected_game_file, expected_mod_file)


@pytest.mark.parametrize("use_symlinks", [True, False])
def test_conflicting_plugins_disable(use_symlinks):
    """
    Install two mods with the same files. Disable the one that is winning the
    conflict for the plugin.

    Test that the plugin isn't removed from the controller's plugins.
    """
    with AmmoController(use_symlinks) as controller:
        # Install both mods
        for mod in [MOD_1, MOD_2]:
            mod_index_download = [i.name for i in controller.downloads].index(
                mod + ".7z"
            )
            controller.install(mod_index_download)

            mod_index = [i.name for i in controller.mods].index(mod)

            controller.activate("mod", mod_index)
            controller.commit()

        # plugin is disabled, changes were not / are not committed
        controller.deactivate("mod", 1)
        assert (
            len(controller.plugins) == 1
        ), "Deactivating a mod hid a plugin provided by another mod"

        # plugin is enabled, changes were / are committed
        controller.activate("mod", 1)
        controller.activate("plugin", 0)
        controller.commit()
        controller.deactivate("mod", 1)
        controller.commit()
        assert (
            len(controller.plugins) == 1
        ), "Deactivating a mod hid a plugin provided by another mod"

        # ensure the plugin points at mod 0.
        if (plugin := controller.game.data / "mock_plugin.esp").is_symlink():
            # Symlink
            assert plugin.readlink() == (
                (controller.mods[0].location / "Data/mock_plugin.esp")
            ), "Plugin pointed to the wrong mod!"
        else:
            # Hardlink
            plugin_stat = os.stat(plugin)
            expected_stat = os.stat(
                controller.mods[0].location / "Data/mock_plugin.esp"
            )
            assert (
                plugin_stat.st_ino == expected_stat.st_ino
            ), f"Expected inode and actual inode differ! {plugin}"


def test_conflicting_plugins_delete():
    """
    Install two mods with the same files. Delete the one that is winning the
    conflict for the plugin.

    Test that the plugin isn't removed from the controller's plugins.
    """
    with AmmoController() as controller:
        # Install both mods
        for mod in [MOD_1, MOD_2]:
            mod_index_download = [i.name for i in controller.downloads].index(
                mod + ".7z"
            )
            controller.install(mod_index_download)
            mod_index = [i.name for i in controller.mods].index(mod)
            controller.activate("mod", mod_index)
            controller.commit()

        # plugin is disabled, changes were not / are not committed
        controller.delete("mod", 1)
        assert (
            len(controller.plugins) == 1
        ), "Deleting a mod hid a plugin provided by another mod"
