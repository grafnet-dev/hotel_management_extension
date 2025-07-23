/** @odoo-module */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

console.log("🔥 DEBUT - test_debug.js chargé !");

export class TestDebug extends Component {
    setup() {
        console.log("🟢 TestDebug - setup() appelé");
    }
}

TestDebug.template = "hotel_management_extension.TestDebug";

console.log("🔥 AVANT - Enregistrement dans le registry");
registry.category("actions").add("test_debug_action", TestDebug);
console.log("🔥 APRES - Enregistrement terminé");

// Vérifier si l'action est bien enregistrée
setTimeout(() => {
    const actions = registry.category("actions");
    console.log("🔍 Actions disponibles:", actions.getAll());
    console.log("🔍 test_debug_action existe?", actions.contains("test_debug_action"));
}, 1000);