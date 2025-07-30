/** @odoo-module **/

console.log("=== TEST SIMPLE HOTEL JS CHARGÉ ===");

// Test basique d'enregistrement
try {
    const { registry } = odoo.loader.modules.get("@web/core/registry");
    console.log("Registry trouvé:", registry);
    
    // Enregistrement simple
    registry.category("actions").add("test.hotel", function() {
        console.log("Action test.hotel appelée!");
        return { type: 'ir.actions.act_window_close' };
    });
    
    console.log("=== ACTION test.hotel ENREGISTRÉE ===");
} catch (error) {
    console.error("Erreur:", error);
}