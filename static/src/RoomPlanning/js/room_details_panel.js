/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class RoomDetailsPanel extends Component {
  static template = "rooms_planning.details_panel";
  static props = ["activity", "close"];

  setup() {
    this.action = useService("action");
    this.notification = useService("notification");
  }

  // Retourne l'icône selon le type d'activité
  getTypeIcon(type) {
    const icons = {
      stay_ongoing: "🛏️",
      upcoming_stay: "📅",
      cleaning: "🧹",
      maintenance: "🔧",
      day_use: "⏱️",
      free_slot: "➖",
    };
    return icons[type] || "📋";
  }

  // Retourne le nom lisible selon le type d'activité
  getTypeName(type) {
    const names = {
      stay_ongoing: "Séjour en cours",
      upcoming_stay: "Séjour à venir",
      cleaning: "Nettoyage programmé",
      maintenance: "Maintenance",
      day_use: "Court séjour",
      free_slot: "Créneau libre",
    };
    return names[type] || "Activité";
  }

  // Formate une date au format lisible
  formatDate(dateString) {
    if (!dateString) return "Non défini";
    
    try {
      const date = new Date(dateString);
      const options = {
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      };
      return date.toLocaleDateString("fr-FR", options);
    } catch (e) {
      return dateString;
    }
  }

  // Ouvre la vue détaillée du séjour
  async onViewDetails() {
    const activity = this.props.activity;
    console.log("👀 Voir détails :", activity);

    if (activity.type === "upcoming_stay" || activity.type === "stay_ongoing") {
      if (!activity.id) {
        this.notification.add("Impossible d'ouvrir les détails : ID manquant.", {
          type: "warning",
        });
        return;
      }

      try {
        await this.action.doAction({
          type: "ir.actions.act_window",
          name: "Détails du séjour",
          res_model: "hotel.booking.stay",
          res_id: activity.id,
          views: [[false, "form"]],
          target: "current",
        });
        
        // Ferme le panneau après l'ouverture
        this.props.close();
      } catch (err) {
        console.warn("⚠️ doAction interrompu ou erreur :", err);
      }
    } else {
      this.notification.add("Aucun séjour lié à cet élément.", {
        type: "info",
      });
    }
  }

  // Ouvre le formulaire d'édition de la réservation
  async onEditReservation() {
    const activity = this.props.activity;
    console.log("✏️ Éditer :", activity);

    if (activity.type === "upcoming_stay" || activity.type === "stay_ongoing") {
      if (!activity.id) {
        this.notification.add("Impossible d'éditer : ID manquant.", {
          type: "warning",
        });
        return;
      }

      try {
        await this.action.doAction({
          type: "ir.actions.act_window",
          name: "Modifier la réservation",
          res_model: "hotel.booking.stay",
          res_id: activity.id,
          views: [[false, "form"]],
          target: "new",
          context: { edit_mode: true },
        });

        console.log("✅ Formulaire d'édition ouvert");
        
        // Optionnel : rafraîchir après fermeture
        // Note: Dans un vrai cas, il faudrait écouter la fermeture du formulaire
      } catch (err) {
        console.warn("⚠️ doAction interrompu ou erreur :", err);
      }
    } else {
      this.notification.add("Aucune réservation à éditer pour cet élément.", {
        type: "warning",
      });
    }
  }
}
