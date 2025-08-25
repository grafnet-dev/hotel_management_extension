/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { roomBookingList } from "../data/bookings";
import { useStore } from "../hooks/useStore";
import { ReservationFormModal } from "./reservation_form_modal/reservation_form_modal";

export class ReservationList extends Component {
  static template = "hotel_management_extension.ReservationList";
  static components = { ReservationFormModal };
  static props = {
    onSelect: Function,
  };

  setup() {
    const { state, actions } = useStore();
    this.state = state;
    this.actions = actions;
    console.log("🧪 store state (reservations):", this.state.reservations);

    // 👇 showModal devient un état réactif
    this.ui = useState({ showModal: false });

    this.handleSelect = (booking) => {
      console.log("📤 Reservation selected:", booking);
      if (!this.props.onSelect) {
        console.error("❌ onSelect prop is missing!");
        return;
      }
      this.props.onSelect(booking);
    };

    this.handleNewReservation = () => {
      console.log("🟢 Ouverture du modal de réservation");
      this.ui.showModal = true;
    };

    this.handleCloseModal = () => {
      console.log("🔴 Fermeture du modal de réservation");
      this.ui.showModal = false;
    };
  }

  get bookings() {
    //ici on enrichit les bookings avec les données des clients et des séjours pour l'affichage
    const bookings = this.state.reservations.bookings.map((booking) => {
      // Récupérer le client complet
      const clients = this.state.clients?.list || [];
      const client = clients.find((c) => c.id === booking.client_id) || {
        id: null,
        name: "Client inconnu",
      };

      //  Mapper les séjours
      const staysData = this.state.reservations?.stays || [];
      const stays = booking.stay_ids
        .map((stayId) => {
          const s = staysData.find((st) => st.id === stayId);
          return s
            ? {
                ...s,
                checkin_date: s.check_in,
                checkout_date: s.check_out,
                room_name: s.room_details?.name || "Inconnu",
                room_type: s.room_details?.bed_type || "Type inconnu",
              }
            : null;
        })
        .filter(Boolean); // éviter les undefined

      // 🔹 Normaliser les champs sensibles (dates, totaux)
      const bookingDate = booking.booking_date
        ? new Date(booking.booking_date)
        : null;

      const totalValue =
        typeof booking.total === "number"
          ? booking.total
          : stays.reduce((sum, s) => sum + (s.total || 0), 0);

      // Retourner booking enrichi
      return {
        ...booking,
        client: client || { name: "Client inconnu" }, // fallback pour éviter l'erreur
        stays,
        booking_date: bookingDate,
        total: totalValue,
        text_de_test: "AYOKPA",
      };
    });

    console.log("📌 Bookings enrichis pour affichage dans le composant de list directement  :", bookings);

    // 🔍 Détection rapide des bookings incomplets
    bookings.forEach((b) => {
      if (!b.booking_date) {
        console.warn("⚠️ booking_date manquant pour booking", b.id);
      }
      if (typeof b.total !== "number") {
        console.warn("⚠️ total invalide pour booking", b.id, b.total);
      }
    });
    return bookings;
  }
}
