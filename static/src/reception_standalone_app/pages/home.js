/** @odoo-module **/

import { Component } from "@odoo/owl";

export class HomePage extends Component {
    static template = "hotel_management_extension.HomePage";
    static props = {}; 

    setup() {
        console.log("🏠 HomePage setup - Composant monté !");
    }
    
    mounted() {
        console.log("✅ HomePage mounted - Composant affiché dans le DOM !");
    }
    
    patched() {
        console.log("🔄 HomePage patched - Composant mis à jour !");
    }
}