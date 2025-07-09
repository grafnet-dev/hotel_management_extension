/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc"; // Import correct pour Odoo 16+

class HotelUIApp extends Component {
  static template = "hotel_ui.template";

  setup() {
    this.rooms = [];

    onWillStart(async () => {
      try {
        this.rooms = await rpc("/web/dataset/call_kw", {
          model: "hotel.room",
          method: "search_read",
          args: [[["is_available", "=", true]], ["name", "price"]],
          kwargs: {}
        });
        console.log("Chambres chargées:", this.rooms);
      } catch (error) {
        console.error("Erreur lors du chargement des chambres:", error);
        this.rooms = [];
      }
    });
  }

  async bookRoom(roomId) {
    try {
      await rpc("/web/dataset/call_kw", {
        model: "hotel.room",
        method: "write",
        args: [[roomId], {"is_available": false}],
        kwargs: {}
      });
      alert("Chambre réservée !");
    } catch (error) {
      console.error("Erreur lors de la réservation:", error);
      alert("Erreur lors de la réservation");
    }
  }
}

registry.category("actions").add("hotel_ui.app", HotelUIApp);
console.log("hotel_ui.app enregistré avec succès!");

  /*async bookRoom(roomId) {
    try {
      await rpc("/web/dataset/call_kw", {
        model: "hotel.room",
        method: "book_now", // Appel d'une méthode personnalisée en Python
        args: [[roomId]],
        kwargs: {}
      });
      alert("Chambre réservée !");
    } catch (error) {
      console.error("Erreur lors de la réservation:", error);
      alert("Erreur lors de la réservation");
    }
  }*/



// Enregistrer le composant pour qu'il puisse être lancé depuis le menu
//registry.category("actions").add("hotel_ui.app", HotelUIApp);