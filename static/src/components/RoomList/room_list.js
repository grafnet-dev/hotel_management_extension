/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import roomsData from "../../data/rooms_data.js"; // 🔧 IMPORT DU MODULE JS

export class RoomList extends Component {
    setup() {
        this.rooms = useState({
            loading: true,
            items: []
        });

        onWillStart(async () => {
            console.log("🟡 Début de la phase onWillStart");
            console.log("🕐 Chargement simulé en cours...");
            
            // Simulation d'attente
            await new Promise(resolve => setTimeout(resolve, 1000));

            // 🔧 CHARGEMENT DEPUIS LE MODULE JS
            this.rooms.items = roomsData;
            this.rooms.loading = false;

            console.log("✅ Données chargées depuis module JS :");
            console.table(this.rooms.items);
        });
    }
}

RoomList.template = "hotel_management_extension.RoomList";
registry.category("actions").add("room_list_action", RoomList);