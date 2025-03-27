(() => {
    "use strict";

    !function() {
        // Default settings
        const DEFAULT_SETTINGS = {
            recaptcha_auto_open: true,
            recaptcha_auto_solve: true,
            recaptcha_click_delay_time: 300,
            recaptcha_solve_delay_time: 1000
        };

        async function initializeDefaultSettings() {
            try {
                const currentSettings = await chrome.storage.local.get(null);
                const newSettings = { ...DEFAULT_SETTINGS };  // Start with all defaults
                
                // Only keep existing values from currentSettings
                for (const key of Object.keys(DEFAULT_SETTINGS)) {
                    if (currentSettings[key] !== undefined) {
                        newSettings[key] = currentSettings[key];
                    }
                }
                
                // Save all settings
                await chrome.storage.local.set(newSettings);
                return newSettings;
            } catch (error) {
                console.error('Failed to initialize settings:', error);
                return DEFAULT_SETTINGS;
            }
        }

        async function handleSettingsChange(element) {
            try {
                // For toggles, we want to switch the state
                const isToggle = element.classList.contains("settings_toggle");
                const currentValue = isToggle ? element.classList.contains("on") : parseInt(element.value);
                const newValue = isToggle ? !currentValue : currentValue;

                // Save to storage
                await chrome.storage.local.set({
                    [element.dataset.settings]: newValue
                });

                // Update UI for toggles
                if (isToggle) {
                    element.classList.remove("on", "off");
                    element.classList.add(newValue ? "on" : "off");
                }
            } catch (error) {
                console.error('Failed to update setting:', error);
            }
        }

        async function initializeSettings() {
            try {
                const settings = await initializeDefaultSettings();
                
                // Initialize toggle elements
                const toggleElements = document.getElementsByClassName("settings_toggle");
                Array.from(toggleElements).forEach(element => {
                    const settingValue = settings[element.dataset.settings];
                    element.classList.remove("on", "off");
                    element.classList.add(settingValue ? "on" : "off");
                    
                    // Add click listener
                    element.addEventListener("click", () => handleSettingsChange(element));
                });

                // Initialize text elements
                const textElements = document.getElementsByClassName("settings_text");
                Array.from(textElements).forEach(element => {
                    const settingValue = settings[element.dataset.settings];
                    if (settingValue !== undefined) {
                        element.value = settingValue;
                    }
                    
                    // Add input listener
                    element.addEventListener("input", () => handleSettingsChange(element));
                });

            } catch (error) {
                console.error('Failed to initialize settings:', error);
            }
        }

        // Wait for DOM to be ready
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", initializeSettings);
        } else {
            initializeSettings();
        }
    }();
})();