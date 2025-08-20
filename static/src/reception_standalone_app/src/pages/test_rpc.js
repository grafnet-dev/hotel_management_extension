/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

export class TestRPC extends Component {
    static template = "hotel_management_extension.TestRPC";
    setup() {
        this.state = useState({
            partners: [],
        });

        // Charger les partenaires avant le rendu
        onWillStart(async () => {
            console.log("Appel RPC en cours vers res.partner...");
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
}