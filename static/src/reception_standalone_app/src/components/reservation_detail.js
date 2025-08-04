/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { PoliceFormModal } from "../components/police_form/police_form_modal";

export class ReservationDetail extends Component {
  static template = "hotel_management_extension.ReservationDetail";
  static components = { PoliceFormModal };
  static props = {
    booking: Object,
    onBack: Function,
  };

  setup() {
  // état local pour afficher/fermer le modal
    this.state = useState({
      showPoliceForm: false,
      selectedStay: null,
      policeForms: {}  // <-- pour stocker les fiches par stay.id
    });

     // Ouvre le modal
    this.triggerCheckin = (stay) => {
      this.state.showPoliceForm = true;
      this.state.selectedStay = stay;
    };

    // Ferme le modal
    this.closeFormModal = () => {
      this.state.showPoliceForm = false;
      this.state.selectedStay = null;
    };
  
    // Valide la fiche police
    this.handleFormValidate = (formData) => {
    const stay = this.state.selectedStay;

    // Enregistre les données de la fiche dans l'état local (mock)
    this.state.policeForms[stay.id] = formData;

    // Met à jour le statut du séjour localement
    stay.status = "checked_in";

    // Ferme le modal
    this.closeFormModal();
  };

  
}

}
