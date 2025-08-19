/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useStore } from "../../hooks/useStore";

export class ReservationFormModal extends Component {
  static template = "hotel_management_extension.ReservationFormModal";
  static props = {
    onClose: Function,
  };

  setup() {
    console.log("🟠 ReservationFormModal.setup() appelé");

    // Récupération du store global
    const { state, actions, getters } = useStore();
    this.state = state;
    this.actions = actions;
    this.getters = getters;

    console.log("📦 Store.state dans ReservationFormModal:", this.state);
    console.log("🔧 Store.actions disponibles:", this.actions);
    console.log("📊 Store.getters disponibles:", this.getters);

    // État local du modal
    this.localState = useState({
      selectedClientId: null,
      stayForm: {
        room_id: null,
        check_in: null,
        check_out: null,
      },
      draftStays: [],
    });
    console.log(
      "🧾 Initialisation de localState dans le modal :",
      this.localState
    );
  }
  addDraftStay() {
    const stay = { ...this.localState.stayForm };
    console.log("➕ Tentative d'ajout de séjour :", stay);

    if (!stay.room_id || !stay.check_in || !stay.check_out) {
      console.warn("⛔ Veuillez remplir tous les champs du séjour.");
      return;
    }

    this.localState.draftStays.push(stay);
    console.log("📦 Séjour ajouté à draftStays :", stay);
    console.log("📊 État actuel de draftStays :", this.localState.draftStays);

    // Reset du formulaire de séjour
    this.localState.stayForm = {
      room_id: null,
      check_in: null,
      check_out: null,
    };
  }

  save() {
    console.log("✅ Bouton Enregistrer cliqué...📤 Envoi du formulaire...");
    console.log("📤 Tentative d'enregistrement du formulaire...");
    console.log(
      "👤 ID du client sélectionné :",
      this.localState.selectedClientId
    );
    console.log("Séjours draft enregistrés :", this.localState.draftStays);

    const clientId = this.localState.selectedClientId;
    const stays = this.localState.draftStays;

    if (!clientId) {
      console.warn("⛔ Aucun client sélectionné !");
      return;
    }

    if (stays.length === 0) {
      console.warn("⛔ Aucun séjour ajouté !");
      return;
    }

    // Création de la réservation
    const bookingId = this.actions.addBooking({
      client_id: clientId,
      booking_date: new Date().toISOString(),
    });

    console.log(`📘 Réservation créée avec ID : ${bookingId}`);

    // 2️⃣ Ajout des séjours bruts (enrichissement automatique dans addStay)
    const stayIds = [];
    /*for (const enrichedStay of enrichedStays) {
      const stayId = this.actions.addStay(bookingId, enrichedStay);
      stayIds.push(stayId);
    }*/
   for (const stay of stays) {
      const stayId = this.actions.addStay(bookingId, stay);
      stayIds.push(stayId);
    }

    // Résumé final
    console.log("✅ Réservation complète !");
    console.log("🧾 Résumé :");
    console.log("Client ID :", clientId);
    //console.log("Séjours :", enrichedStays);
    console.log("Stay IDs :", stayIds);
    console.log("Réservation ID :", bookingId);

    this.props.onClose(); // Ferme la modal via la prop du parent
  }

  close() {
    console.log("❌ Bouton Annuler cliqué");
    console.log("🔴 Fermeture de la modal demandée");
    this.props.onClose(); // Ferme la modal via la prop du parent
  }
}
