/** @odoo-module **/

import { Component } from "@odoo/owl";

export class AboutPage extends Component {
    static template = "hotel_management_extension.AboutPage";
    static props = {
        name: { type: String, optional: true },
        // Ajout d'une prop par défaut pour éviter les erreurs
        "*": true, // Accepte toutes les autres props
    };

    setup() {
        console.log("ℹ️ AboutPage setup - Composant monté !");
        console.log("ℹ️ AboutPage setup - Props:", this.props);
        
        // Vérification des props pour debug
        if (!this.props) {
            console.warn("⚠️ AboutPage: Props est undefined !");
        }
    }
    
    mounted() {
        console.log("✅ AboutPage mounted - Composant affiché dans le DOM !");
    }
    
    patched() {
        console.log("🔄 AboutPage patched - Composant mis à jour !");
    }
}