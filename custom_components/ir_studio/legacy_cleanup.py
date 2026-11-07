"""One-time cleanup of unused cloud-name placeholders from pre-1.0 profiles.

Only removals explicitly safe for unused placeholders: verified/learned/unknown
codes, user-created buttons, and profiles containing real content are retained.
"""
from __future__ import annotations

CLOUD_ONLY_ORIGINS = frozenset({
    "tuya_device_mapping", "tuya_device_specification", "tuya_ir_remote_keys",
    "tuya_account_mapping", "tuya_export_mapping", "tuya_cloud_key_metadata",
})


def clean_cloud_placeholders(profiles, ir_codes, native_codes) -> tuple[int, int]:
    """Mutate profiles in place, return (#removed_buttons, #removed_profiles).

    Do not remove a button when there might be an actual IR code. Remote
    entities outside our own CodeStores cannot be positively inspected here,
    so remove only explicit *pending*, unverified cloud-only placeholders.
    """
    removed_buttons = removed_profiles = 0
    retained_profiles = []
    for profile in profiles:
        buttons = profile.get("buttons", [])
        retained = []
        removed_from_profile = 0
        for button in buttons:
            key = f"{profile.get('id')}/{button.get('id')}"
            cloud_only = button.get("origin") in CLOUD_ONLY_ORIGINS
            has_code = key in ir_codes or key in native_codes
            if (cloud_only and button.get("status") == "pending"
                    and not button.get("verified") and not has_code):
                removed_buttons += 1
                removed_from_profile += 1
            else:
                retained.append(button)
        if removed_from_profile:
            profile["buttons"] = retained
        # Only remove a profile that became empty from actual placeholder
        # cleanup. Never delete an already-empty profile merely because it
        # still carries legacy account metadata (it may be user-maintained).
        # A detached code can still be useful if the user repairs the
        # profile later. Keep the profile rather than orphaning its waveform.
        profile_prefix = f"{profile.get('id')}/"
        has_profile_codes = any(
            key.startswith(profile_prefix)
            for store in (ir_codes, native_codes)
            for key in store
        )
        if (removed_from_profile > 0
                and not retained
                and not has_profile_codes
                and profile.get("account_origin") == "tuya_sharing_device_metadata"
                and profile.get("account_ref")):
            removed_profiles += 1
            continue
        retained_profiles.append(profile)
    if removed_buttons or removed_profiles:
        profiles[:] = retained_profiles
    return removed_buttons, removed_profiles
