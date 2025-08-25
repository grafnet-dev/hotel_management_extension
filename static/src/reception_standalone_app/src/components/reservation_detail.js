/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { PoliceFormModal } from "../components/police_form/police_form_modal";
import { useStore } from "../hooks/useStore";

export class ReservationDetail extends Component {
  static template = "hotel_management_extension.ReservationDetail";
  static components = { PoliceFormModal };
  static props = {
    booking: Object,
    onBack: Function,
  };

  setup() {
    // Récupération du store global
    const { state, actions, getters } = useStore();
    this.state = state;
    this.actions = actions;
    this.getters = getters;

    // état local
    this.state = useState({
      showPoliceForm: false,
      activeStay: null,
    });

    // Ouvre le modal
    this.triggerCheckin = (stay) => {
      console.log("🟢 [triggerCheckin] Stay sélectionné :", stay);
      
      if (!stay) {
        console.warn("⚠️ [triggerCheckin] Aucun séjour sélectionné");
        return;
      }
      //on stocke ici le séjour concerné
      this.state.activeStay = stay;
      this.state.showPoliceForm = true;

      console.log("🔵 [triggerCheckin] State local après ouverture :", this.state);
    };

    // Ferme le modal sans rien valider
    this.handleCancel = () => {
      console.log("🟡 [handleCancel] Fermeture modal sans validation");

      this.state.showPoliceForm = false;
      this.state.activeStay = null;

      console.log("🔵 [handleCancel] State après reset :", this.state);
    };

    // Validation du formulaire
    this.handleFormValidate = (formData) => {
      console.log(
        "🟢 [handleFormValidate] Données reçues du modal :",
        formData
      );

      const stayId = this.state.activeStay?.id;
      console.log("🔑 [handleFormValidate] StayId ciblé :", stayId);

      this.actions.addPoliceForm(stayId, formData);
      console.log("✅ [handleFormValidate] addPoliceForm exécuté");

      this.actions.updateStayStatus(stayId, "checked_in");
      console.log("✅ [handleFormValidate] updateStayStatus exécuté");

      this.state.showPoliceForm = false;
      this.state.activeStay = null;

      console.log(
        "🔵 [handleFormValidate] State après validation :",
        this.state
      );
    };
  }
}
