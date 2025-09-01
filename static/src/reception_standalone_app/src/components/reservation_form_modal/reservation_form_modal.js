/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useStore } from "../../hooks/useStore";
import { methodCall } from "../../services/api";

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
        reservation_type_id: null,
        room_id: null,
        booking_start_date: null,
        booking_end_date: null,
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

  // Propriété calculée pour la compatibilité avec le template
  get isFlexibleReservation() {
  const resaTypeId = this.localState.stayForm.reservation_type_id;
  if (!resaTypeId) {
    console.log("🔍 isFlexibleReservation: aucun type sélectionné → false");
    return false;
  }

  const resaType = this.state.reservation_types.list.find(r => r.id == resaTypeId);

  if (!resaType) {
    console.log(`🔍 isFlexibleReservation: type ${resaTypeId} introuvable → false`);
    return false;
  }

  console.log(
    `🔍 isFlexibleReservation: type=${resaType.name} (id=${resaType.id}), flexible=${resaType.is_flexible}`
  );
  return resaType.is_flexible;
}


  get currentReservationType() {
    const resaTypeId = this.localState.stayForm.reservation_type_id;
    if (!resaTypeId) return null;
    return this.state.reservation_types.list.find((r) => r.id == resaTypeId);
  }

  // Méthode appelée quand le type de réservation change
  onReservationTypeChange() {
    console.log("🔄 Type de réservation changé");
    
    // Reset des champs de dates quand on change le type
    this.localState.stayForm.booking_start_date = null;
    this.localState.stayForm.booking_end_date = null;
    this.localState.stayForm.check_in = null;
    this.localState.stayForm.check_out = null;
    
    console.log("✅ Champs de dates réinitialisés");
  }

  // Méthode pour formater les dates pour datetime-local
  formatDateTimeLocal(dateTimeString) {
    if (!dateTimeString) return "";
    
    // Si c'est déjà au bon format, on le retourne
    if (dateTimeString.includes("T")) {
      return dateTimeString.slice(0, 16); // Format YYYY-MM-DDTHH:MM
    }
    
    // Sinon on convertit depuis le format date
    const date = new Date(dateTimeString);
    return date.toISOString().slice(0, 16);
  }

  // Méthode pour mettre à jour les booking_dates depuis check_in/check_out (pour flexible)
  onFlexibleDateChange() {
    if (this.isFlexibleReservation) {
      const { check_in, check_out } = this.localState.stayForm;
      
      if (check_in) {
        this.localState.stayForm.booking_start_date = check_in.split('T')[0];
      }
      if (check_out) {
        this.localState.stayForm.booking_end_date = check_out.split('T')[0];
      }
      
      console.log("🔄 Dates booking mises à jour depuis check-in/out flexibles");
    }
  }

  async computeDatesFromBackend() {
    console.log("⚙️ computeDatesFromBackend() appelé");

    const { room_id, reservation_type_id, booking_start_date, booking_end_date } =
      this.localState.stayForm;

    if (!room_id || !reservation_type_id || !booking_start_date || !booking_end_date) {
      console.warn("⛔ Champs manquants pour le calcul checkin/checkout");
      return;
    }

    // Ne pas calculer si c'est une réservation flexible
    if (this.isFlexibleReservation) {
      console.log("🔄 Réservation flexible - pas de calcul automatique");
      return;
    }

    const room = this.state.rooms.list.find((r) => r.id == room_id);
    if (!room) {
      console.warn("⛔ Chambre introuvable dans le state");
      return;
    }

    const payload = {
      room_type_id: 1, // attention : ton modèle doit avoir room_type_id dispo !
      reservation_type_id: Number(reservation_type_id),
      booking_start_date,
      booking_end_date,
    };
    console.log("📤 Payload envoyé au RPC compute_checkin_checkout :", payload);

    try {
      const result = await methodCall(
        "hotel.booking.stay",         
        "compute_checkin_checkout", 
        [payload]                           
      );

      console.log("📥 Résultat RPC via methodCall :", result);

      if (result.success) {
        // Formater les dates pour datetime-local
        this.localState.stayForm.check_in = this.formatDateTimeLocal(result.data.checkin_date);
        this.localState.stayForm.check_out = this.formatDateTimeLocal(result.data.checkout_date);
        console.log("✅ Dates mises à jour dans stayForm :", this.localState.stayForm);
      } else {
        console.warn("⚠️ Erreur côté RPC :", result.message);
      }
    } catch (err) {
      console.error("🚨 Erreur RPC :", err);
    }
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
      reservation_type_id: null,
      room_id: null,
      booking_start_date: null,
      booking_end_date: null,
      check_in: null,
      check_out: null,
    };
  }

  async save() {
    console.log("✅ Bouton Enregistrer cliqué...📤 Envoi du formulaire...");

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

    try {
      // 1️⃣ Création du booking côté backend (Odoo)
      const bookingId = await this.actions.createBooking({
        client_id: clientId,
        booking_date: new Date().toISOString(),
      });

      console.log(`📘 Réservation créée avec ID Odoo : ${bookingId}`);

      // 2️⃣ Ajout des séjours en local (pas envoyés à Odoo pour l'instant)
      const stayIds = [];
      for (const stay of stays) {
        const stayId = this.actions.addStay(bookingId, stay);
        stayIds.push(stayId);
      }

      // 3️⃣ Résumé final
      console.log("✅ Réservation complète !");
      console.log("🧾 Résumé :");
      console.log("Client ID :", clientId);
      console.log("Stay IDs :", stayIds);
      console.log("Réservation ID :", bookingId);

      this.props.onClose(); 
    } catch (error) {
      console.error("🚨 Erreur lors de la création du booking :", error);
      alert("Impossible de créer la réservation : " + error.message);
    }
  }
}