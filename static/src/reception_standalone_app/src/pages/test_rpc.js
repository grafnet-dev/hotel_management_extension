/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

export class TestRPC extends Component {
    static template = "hotel_management_extension.TestRPC";

    setup() {
        this.state = useState({
            partners: [],
            lastStay: null,  
        });

        // Charger quelques partenaires avant le rendu
        onWillStart(async () => {
            console.log("Appel RPC en cours...");
            try {
                const partners = await rpc("/web/dataset/call_kw/", {
                    model: "res.partner",
                    method: "search_read",
                    args: [],
                    kwargs: {
                        fields: ["id", "name", "email"],
                        limit: 5,
                    },
                });
                console.log("Réponse RPC reçue:", partners);
                this.state.partners = partners;
            } catch (err) {
                console.error("Erreur RPC:", err);
            }
        });
    }

  async createStay() {
    console.log("➡️ Tentative de création d’un stay...");
    try {
        const stay = await rpc("/web/dataset/call_kw/", {
            model: "hotel.booking.stay",
            method: "create_stay_from_ui",
            args: [{
                booking_id: 1,            // ID existant dans room.booking
                room_type_id: 1,          // ID existant dans hotel.room.type
                reservation_type_id: 3,   // ID existant dans hotel.reservation.type
                booking_start_date: "2025-09-01",
                booking_end_date: "2025-09-05",
            }],
            kwargs: {},
        });
        console.log("✅ Stay créé :", stay);
        this.state.lastStay = stay;
    } catch (err) {
        console.error("❌ Erreur création stay:", err);
    }
}

}
