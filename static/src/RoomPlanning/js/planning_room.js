/** @odoo-module **/

import { Component, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class RoomPlanning extends Component {
  static template = "rooms_planning.template";

  setup() {
    this.rooms = Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      name: `A${String(i + 1).padStart(3, "0")}`,
    }));

    this.activities = this.generateMockActivities();

    onMounted(() => {
      console.log("✅ Composant RoomPlanning monté !");
      const container = document.getElementById("room-timeline");
      if (!container) {
        console.error("❌ Conteneur introuvable !");
        return;
      }
      console.log("🎯 Conteneur trouvé :", container);

      // Vérif que vis-timeline est dispo
      if (!(window.vis && window.vis.Timeline)) {
        console.error("❌ vis-timeline n'est pas chargé !");
        return;
      }
      console.log("🚀 vis-timeline est bien chargé !");

      // 👉 Transformer rooms → groups
      this.groups = this.rooms.map((r) => ({
        id: r.id,
        content: r.name,
      }));
      console.log("📦 Groups générés :", this.groups);

      // 👉 Transformer activities → items
      this.items = this.activities.map((a) => ({
        id: a.id,
        group: a.room_id,
        start: a.start,
        end: a.end,
        content: `${this.getTypeIcon(a.type)} ${a.guest}`,
        style: `background-color: ${a.color};`,
      }));
      console.log("📦 Items générés :", this.items);

      // 👉 Options vis-timeline (d’après ton snippet)
      const now = new Date();
      const options = {
        stack: false,
        horizontalScroll: true,
        zoomKey: "ctrlKey",
        min: new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7),
        max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 14),
        zoomMin: 1000 * 60 * 60, // 1h
        zoomMax: 1000 * 60 * 60 * 24 * 31, // 1 mois
      };

      // ✅ Création de la timeline et stockage dans l'instance
      this.timeline = new vis.Timeline(
        container,
        this.items,
        this.groups,
        options
      );
      console.log("📅 Timeline initialisée avec succès !");
    });
    onWillUnmount(() => {
      if (this.timeline) {
        this.timeline.destroy();
        console.log("🧹 Timeline détruite proprement");
      }
    });
  }
  // ---- Fonctions utilitaires ----
  generateMockActivities() {
    const now = new Date();
    return [
      {
        id: 1,
        room_id: 1,
        type: "booking",
        start: new Date(
          now.getFullYear(),
          now.getMonth(),
          now.getDate(),
          14,
          0
        ),
        end: new Date(
          now.getFullYear(),
          now.getMonth(),
          now.getDate() + 1,
          11,
          0
        ),
        guest: "Client A",
        color: "#4caf50",
      },
      {
        id: 2,
        room_id: 2,
        type: "cleaning",
        start: new Date(
          now.getFullYear(),
          now.getMonth(),
          now.getDate(),
          11,
          0
        ),
        end: new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0),
        guest: "Nettoyage",
        color: "#ff9800",
      },
    ];
  }
  getTypeIcon(type) {
    const icons = {
      booking: "🛏️",
      cleaning: "🧹",
      maintenance: "🔧",
      day_use: "⏱️",
    };
    return icons[type] || "📋";
  }
}

registry.category("actions").add("room_planning.app", RoomPlanning);

console.log("✅ RoomPlanning avec précision horaire enregistré !");
