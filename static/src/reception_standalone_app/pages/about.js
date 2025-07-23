/** @odoo-module **/

import { Component } from "@odoo/owl";

export class AboutPage extends Component {
    static template = "hotel_management_extension.AboutPage";
    static props = {
        name: { type: String, optional: true },
    };


    setup() {
        console.log("ℹ️ AboutPage setup - Composant monté !");
        console.log("ℹ️ AboutPage setup - Props:", this.props)
    }
    
    mounted() {
        console.log("✅ AboutPage mounted - Composant affiché dans le DOM !");
    }
    
    patched() {
        console.log("🔄 AboutPage patched - Composant mis à jour !");
    }
}
