/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
export class RoomPlanning extends Component {
  static template = "rooms_planning.template";

  setup() {
    this.action = useService("action");
    this.rooms = [];
    this.activities = [];

    // Charger les données AVANT le rendu
    onWillStart(async () => {
      await this.loadData();
    });

    onMounted(() => {
      this.initTimeline();
    });

    onWillUnmount(() => {
      if (this.timeline) {
        this.timeline.destroy();
        console.log("🧹 Timeline détruite proprement");
      }
    });
  }
  // chargement des datas
  async loadData() {
    console.log("📡 Chargement initial (onWillStart)...");

    try {
      // Charger les chambres
      const rooms = await rpc("/web/dataset/call_kw", {
        model: "hotel.room",
        method: "search_read",
        args: [],
        kwargs: {
          fields: ["id", "name", "status"],
        },
      });

      this.rooms = rooms;
      console.log("🏨 Chambres chargées :", this.rooms);

      // Charger les activités pour toutes les chambres en parallèle
      const startDate = "2025-10-01";
      const endDate = "2025-10-30";

      const activityPromises = rooms.map(async (room) => {
        const result = await rpc("/web/dataset/call_kw", {
          model: "hotel.room",
          method: "get_room_activities",
          args: [room.id, startDate, endDate],
          kwargs: {},
        });

        console.log(`📩 Activités chambre ${room.id}:`, result);

        // Retourne un tableau d'activités enrichies avec l'id de la chambre
        return result.success
          ? result.data.map((a) => ({
              ...a,
              room_id: room.id,
              room_name: room.name,
            }))
          : [];
      });
      // Aplatir tous les tableaux d'activités en un seul
      const activitiesNested = await Promise.all(activityPromises);
      this.activities = activitiesNested.flat();

      console.log("✅ Chambres :", this.rooms);
      console.log("✅ Activités :", this.activities);
    } catch (error) {
      console.error("💥 Erreur lors du chargement initial :", error);
      this.rooms = [];
      this.activities = [];
    }
  }
  //initialisation de la timeline
  initTimeline() {
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

    // Transformer rooms → groups
    this.groups = this.rooms.map((r) => ({
      id: r.id,
      content: r.name,
    }));
    console.log("📦 Groups générés :", this.groups);

    // Transformer activities → items (pour vis-timeline)
    this.items = this.activities.map((act) => ({
      id: act.id,
      group: act.room_id,
      room_id: act.room_id,
      content: act.label,
      start: act.start,
      end: act.end,
      className: act.type,
      title: `
        <b>${act.room_name}</b><br>
        ${act.content}<br>
        Du ${act.start} au ${act.end}
        `,
    }));
    console.log ("content  ", this.items.content);
    console.log("🧩 Items générés :", this.items);

    const now = new Date();
    const options = {
      stack: false,
      horizontalScroll: true,
      zoomKey: "ctrlKey",
      min: new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7),
      max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 14),
      zoomMin: 1000 * 60 * 60, // 1h
      zoomMax: 1000 * 60 * 60 * 24 * 31, // 1 mois
       
  orientation: {
    axis: "top",
    item: "bottom",
  },
    };

    // Supprime les doublons d'id avant d'afficher la timeline
    const uniqueItems = [];
    const seenIds = new Set();

    for (const item of this.items) {
      if (!seenIds.has(item.id)) {
        uniqueItems.push(item);
        seenIds.add(item.id);
      } else {
        console.warn("⚠️ ID dupliqué détecté et ignoré :", item.id);
      }
    }

    this.items = uniqueItems;

    // Création de la timeline et stockage dans l'instance 🧹 S’il existe déjà une timeline, la réinitialiser
    if (this.timeline) {
      console.log("♻️ Réinitialisation de la timeline...");
      this.timeline.setItems(new vis.DataSet(this.items));
    } else {
      // Première création
      this.timeline = new vis.Timeline(
        container,
        this.items,
        this.groups,
        options
      );
      console.log("📅 Timeline initialisée avec succès !");
    }
    // 🔹 Gestion du clic
    this.timeline.on("click", (props) => this.onTimelineClick(props));
  }
  //Gestion du click
  onTimelineClick(props) {
    console.log("🖱️ [EVENT] Clic sur timeline → props reçus :", props);

    if (!props.item) {
      console.log("🟣 Clic vide (pas sur un item).");
      return;
    }
    // Recherche de l'objet complet dans la liste this.items
    const clickedItem = this.items.find((i) => i.id === props.item);
    console.log("📦 Item trouvé :", clickedItem);

    if (!clickedItem) {
      console.warn("⚠️ Aucun item correspondant trouvé !");
      return;
    }

    if (clickedItem.className === "free_slot") {
      console.log("✅ Créneau libre → ouverture du formulaire...");
      this.onFreeSlotClick(clickedItem);
    } else {
      console.log("⛔ Item non libre (type :", clickedItem.className, ")");
    }
  }
  onFreeSlotClick(item) {
    console.log("🟢 [onFreeSlotClick] Créneau libre cliqué :", item);

    if (!item.room_id) {
      console.warn("⚠️ Aucun room_id trouvé sur l’item :", item);
      return;
    }

    console.log("🚀 Ouverture du formulaire Odoo pour créer un séjour...");
    this.action
      .doAction({
        type: "ir.actions.act_window",
        name: "Nouvelle réservation",
        res_model: "hotel.booking.stay",
        target: "new",
        views: [[false, "form"]],
        view_mode: "form",
        context: {
          default_room_id: item.room_id,
        },
      })
      .then(async () => {
        console.log(
          "🟢 Fenêtre de réservation fermée, mise à jour du planning..."
        );
        await this.refreshTimeline();
      });

    console.log("✅ Action envoyée à Odoo !");
  }

  async refreshTimeline() {
    console.log("🔄 Rafraîchissement de la timeline...");
    await this.loadData();

    // Recréer les items
    const items = this.activities.map((act) => ({
      id: act.id,
      group: act.room_id,
      room_id: act.room_id,
      content: act.label,
      start: act.start,
      end: act.end,
      className: act.type,
      title: `<b>${act.room_name}</b><br>${act.content}<br>Du ${act.start} au ${act.end}`,
    }));

    if (this.timeline) {
      this.timeline.setItems(new vis.DataSet(items));
      console.log("✅ Timeline mise à jour !");
    }
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
