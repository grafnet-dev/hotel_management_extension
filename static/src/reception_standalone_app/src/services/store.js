import { registry } from "@web/core/registry";
import { AppState } from "../store";
import { generateUniqueId } from "../utils/generate_unique_id";
import {
  BOOKING_STATUS,
  STAY_STATUS,
  bookingTransitions,
  stayTransitions,
} from "../data/statuts";

const SERVICE_NAME = "hm_reception_store";
// (facultatif) actions centralisées
function createActions(state) {
  return {
    /***********************************Action Bookings**************************************************/
    // Créer une nouvelle réservation avec une liste vide de stays.
    addBooking(bookingData) {
      console.log("🟢 [addBooking] Données reçues :", bookingData);

      const id = generateUniqueId();
      const newBooking = {
        id,
        client_id: Number(bookingData.client_id),
        booking_date: bookingData.booking_date || new Date(),
        stay_ids: [], // sera rempli après
        group_code: bookingData.group_code || "DEFAULT_GROUP",
        status: BOOKING_STATUS.PENDING,
        total_booking_amount: 0, // sera calculé plus tard
      };

      // Ajout dans le state
      state.reservations.bookings.push(newBooking);

      console.log("📦 [addBooking] Nouvelle réservation ajoutée :", newBooking);
      console.log(
        `📦 Booking créé (status="${BOOKING_STATUS.PENDING}")`,
        newBooking
      );
      console.log(
        "📂 [addBooking] État actuel des réservations :",
        state.reservations.bookings
      );

      return id;
    },

    // Ajouter un séjour à une réservation, enrichir, calculer les totaux.
    addStay(bookingId, stayData) {
      console.log("🟡 [addStay] bookingId reçu :", bookingId);
      console.log("🟡 [addStay] Données du séjour reçues :", stayData);

      const id = generateUniqueId();

      const stay = {
        id,
        booking_id: bookingId,
        room_id: Number(stayData.room_id),
        occupant_id: null,
        check_in: stayData.check_in,
        check_out: stayData.check_out,
        food_lines: [],
        event_lines: [],
        service_lines: [],
        early_checkin_requested: false,
        late_checkout_requested: false,
        extra_night_required: false,
        notes: "Pas de note",
        status: STAY_STATUS.PENDING,
      };

      console.log("📋 [addStay] Séjour brut créé :", stay);

      // Enrichissement
      const enrichedStay = this.enrichStay(stay);
      console.log(
        `📋 Stay ajouté et ✨ [addStay] Séjour enrichi : (status="${STAY_STATUS.PENDING}")`,
        enrichedStay
      );

      // Ajout dans state
      state.reservations.stays.push(enrichedStay);

      // Lier à la réservation correspondante
      const booking = state.reservations.bookings.find(
        (b) => b.id === bookingId
      );
      if (booking) {
        booking.stay_ids.push(enrichedStay.id);
        console.log(`🔗 [addStay] Séjour lié à la réservation ${bookingId}`);
      } else {
        console.error(
          `❌ [addStay] Réservation non trouvée pour l'ID ${bookingId}`
        );
      }

      console.log(
        `📂 [addStay] État actuel des séjours :pour l'ID ${bookingId}`,
        state.reservations.stays
      );

      return enrichedStay.id;
    },

    // Enrichissement de l'objet stays avec les infos pour l'affichage  room info, totaux etc .
    enrichStay(stay) {
      console.log("🔧 [enrichStay] Enrichissement du séjour :", stay);
      console.log("📌 Liste des chambres :", state.rooms.list);
      console.log("📌 ID de chambre recherché :", stay.room_id);
      // Récupérer la chambre
      const room = state.rooms.list.find((r) => r.id === stay.room_id);
      // Récupérer l'occupant
      let occupant = null;
      if (stay.occupant_id) {
        occupant =
          state.clients.list.find((c) => c.id === stay.occupant_id) || null;
      }
      // Enrichir consommations
      const enrichedFoodLines = state.reservations.foodBookingLines
        .filter((l) => l.stay_id === stay.id)
        .map((l) => this.enrichFoodBookingLine(l));

      const enrichedEventLines = state.reservations.eventBookingLines
        .filter((l) => l.stay_id === stay.id)
        .map((l) => this.enrichEventBookingLine(l));

      const enrichedServiceLines = state.reservations.serviceBookingLines
        .filter((l) => l.stay_id === stay.id)
        .map((l) => this.enrichServiceBookingLine(l));

      /*Simulons les totaux pour l'instant
      const room_price_total = 0; // sera remplacé plus tard par calculateStayTotals
      Calculer le prix total de la chambre
      */
      const room_price_total = this.calculateStayTotals(stay, room);
      // Calculer les totaux consommations
      const consumption_total =
        enrichedFoodLines.reduce((sum, l) => sum + l.food_price_total, 0) +
        enrichedEventLines.reduce((sum, l) => sum + l.event_price_total, 0) +
        enrichedServiceLines.reduce((sum, l) => sum + l.service_price_total, 0);

      if (!room) {
        console.warn(
          "⚠️ [enrichStay] Chambre non trouvée pour l'id :",
          stay.room_id
        );
        if (!occupant) {
          console.warn(
            "⚠️ [enrichStay] Occupant non trouvé pour l'id :",
            stay.occupant_id
          );
        }

        /*return {
          ...stay,
          room_details: null,
          room_price_total: 0,
          consumption_total: 0,
          total_amount: 0,
        };*/
      }
      const enriched = {
        ...stay,
        room_details: room,
        occupant,
        food_lines: enrichedFoodLines,
        event_lines: enrichedEventLines,
        service_lines: enrichedServiceLines,
        room_price_total,
        consumption_total,
        total_amount: room_price_total + consumption_total, // total_amount = room_price_total + consumption_total
      };

      console.log(
        `✅ [enrichStay] Séjour enrichi (status="${stay.status}")`,
        enriched
      );

      return enriched;
    },
    //methode appelée pour assigner un occupant à un séjour lors du checkin
    assignOccupantToStay(stayId, occupantId) {
      const stayIndex = state.reservations.stays.findIndex(
        (s) => s.id === stayId
      );
      if (stayIndex === -1) {
        console.error(`❌ Stay ${stayId} introuvable`);
        return false;
      }

      state.reservations.stays[stayIndex].occupant_id = occupantId;
      state.reservations.stays[stayIndex] = this.enrichStay(
        state.reservations.stays[stayIndex]
      );

      console.log(
        `✅ Occupant assigné au séjour ${stayId}`,
        state.reservations.stays[stayIndex]
      );
      return true;
    },

    /* Calcule le prix de la chambre en fonction des
    dates earlycheckin ,late checkout etc .
    plus tard il ne doit pas retourner que room_price_total 
    mais sans  les autres totaux consumption_total etc.*/
    calculateStayTotals(stay, room) {
      console.log("🧮 Calcul du prix du séjour...");
      console.log("🛏️ Room reçue :", room);
      console.log("📆 Dates reçues :", stay.check_in, "->", stay.check_out);

      if (!stay.check_in || !stay.check_out) {
        console.warn("⚠️ Dates incomplètes pour le séjour.");
        return 0;
      }

      const inDate = new Date(stay.check_in);
      const outDate = new Date(stay.check_out);

      // ⚠️ Éviter les résultats négatifs ou invalides
      if (isNaN(inDate) || isNaN(outDate) || outDate <= inDate) {
        console.warn("⚠️ Dates invalides.");
        return 0;
      }

      const millisecondsPerDay = 1000 * 60 * 60 * 24;
      const nights = Math.ceil((outDate - inDate) / millisecondsPerDay);

      // 🧪 TEMP : valeur en dur pour le prix si room ou room.price est manquant
      const pricePerNight = room?.price ?? 15000;

      const total = nights * pricePerNight;

      console.log(
        `🌙 ${nights} nuit(s) x ${pricePerNight} FCFA = ${total} FCFA`
      );

      return total;
    },

    //mettre à jour le statut d'un booking
    updateBookingStatus(bookingId, newStatus) {
      console.log(
        `🔄 [updateBookingStatus] Tentative de passage Booking ${bookingId} → ${newStatus}`
      );

      const booking = state.reservations.bookings.find(
        (b) => b.id === bookingId
      );
      if (!booking) {
        console.error(`❌ Booking ${bookingId} introuvable`);
        return false;
      }

      const allowed = bookingTransitions[booking.status] || [];
      if (!allowed.includes(newStatus)) {
        console.warn(
          `⚠️ Transition refusée : ${booking.status} → ${newStatus}`
        );
        return false;
      }

      booking.status = newStatus;
      console.log(`✅ Booking ${bookingId} est maintenant "${newStatus}"`);

      // Effet cascade
      if (newStatus === BOOKING_STATUS.CANCELLED) {
        booking.stay_ids.forEach((stayId) => {
          this.updateStayStatus(stayId, STAY_STATUS.CANCELLED);
        });
      }

      return true;
    },

    //mettre à jour le statut d'un stay
    updateStayStatus(stayId, newStatus) {
      console.log(
        `🔄 [updateStayStatus] Tentative de passage Stay ${stayId} → ${newStatus}`
      );

      const stay = state.reservations.stays.find((s) => s.id === stayId);
      if (!stay) {
        console.error(`❌ Stay ${stayId} introuvable`);
        return false;
      }

      const allowed = stayTransitions[stay.status] || [];
      if (!allowed.includes(newStatus)) {
        console.warn(`⚠️ Transition refusée : ${stay.status} → ${newStatus}`);
        return false;
      }

      stay.status = newStatus;
      console.log(`✅ Stay ${stayId} est maintenant "${newStatus}"`);

      // Synchroniser avec le booking parent
      this.syncBookingStatusFromStays(stay.booking_id);

      return true;
    },

    // Synchroniser le statut d'un booking en fonction de celui de ses stays
    syncBookingStatusFromStays(bookingId) {
      console.log(
        `🔄 [syncBookingStatusFromStays] Recalcul du statut Booking ${bookingId}`
      );

      const booking = state.reservations.bookings.find(
        (b) => b.id === bookingId
      );
      if (!booking) {
        console.error(`❌ Booking ${bookingId} introuvable`);
        return;
      }

      const stays = state.reservations.stays.filter((s) =>
        booking.stay_ids.includes(s.id)
      );

      const allCheckedOut = stays.every(
        (s) => s.status === STAY_STATUS.CHECKED_OUT
      );
      const anyCheckedIn = stays.some(
        (s) => s.status === STAY_STATUS.CHECKED_IN
      );
      const allPending = stays.every((s) => s.status === STAY_STATUS.PENDING);
      const allCancelled = stays.every(
        (s) => s.status === STAY_STATUS.CANCELLED
      );

      if (allCancelled) {
        this.updateBookingStatus(bookingId, BOOKING_STATUS.CANCELLED);
      } else if (allCheckedOut) {
        this.updateBookingStatus(bookingId, BOOKING_STATUS.COMPLETED);
      } else if (anyCheckedIn) {
        // 👉 Cas important : check-in alors que booking est encore pending
        if (booking.status === BOOKING_STATUS.PENDING) {
          console.log(
            `🔄 Booking ${bookingId} est encore "pending", on le confirme d'abord`
          );
          this.updateBookingStatus(bookingId, BOOKING_STATUS.CONFIRMED);
        }
        // Ensuite, passage à in_progress
        this.updateBookingStatus(bookingId, BOOKING_STATUS.IN_PROGRESS);
      } else if (allPending) {
        if (
          booking.status === BOOKING_STATUS.CONFIRMED ||
          booking.status === BOOKING_STATUS.PENDING
        ) {
          console.log(`ℹ️ Booking ${bookingId} reste "${booking.status}"`);
        }
      }
    },

    /**************************************Actions CLients********************************************************/
    // Ajouter un client
    addClient(client) {
      // 1. On récupère la liste des ids existants
      const existingIds = state.clients.list.map((c) => c.id);
      // 2. On fabrique un "nouveau client" :
      //    - on génère un id unique
      //    - on fusionne les données du client passé en paramètre
      const newClient = {
        id: generateUniqueId(existingIds),
        ...client,
      };
      // 3. On l’ajoute dans la liste globale du store
      state.clients.list.push(newClient);
      // 4. On retourne son id pour le composant (utile si on veut s’y rattacher)
      return newClient.id;
    },
    // Mettre à jour les informations d'un client
    updateClient(id, updatedClientData) {
      const clientIndex = state.clients.list.findIndex((c) => c.id === id);
      if (clientIndex !== -1) {
        state.clients.list[clientIndex] = {
          ...state.clients.list[clientIndex],
          ...updatedClientData,
        };
        return state.clients.list[clientIndex];
      }
      return null;
    },
    // Supprimer un client
    deleteClient(id) {
      const clientIndex = state.clients.list.findIndex((c) => c.id === id);
      if (clientIndex !== -1) {
        state.clients.list.splice(clientIndex, 1);
        return true;
      }
      return false;
    },

    /**************************************Actions Stays Consumptions********************************************************/

    // Ajouter une ligne Food
    addFoodBookingLine(lineData) {
      console.log("🍽️ [addFoodBookingLine] Données reçues :", lineData);

      const id = generateUniqueId();
      const total = lineData.qty * lineData.price_unit;

      const newLine = {
        id,
        stay_id: lineData.stay_id,
        food_id: lineData.food_id,
        description: lineData.description || "",
        qty: lineData.qty,
        price_unit: lineData.price_unit,
        food_price_total: total,
      };

      state.reservations.foodBookingLines.push(newLine);

      console.log("✅ [addFoodBookingLine] Ligne brute ajoutée :", newLine);
      console.log(
        "📂 État actuel des foodBookingLines :",
        state.reservations.foodBookingLines
      );

      // On met aussi l'ID dans le séjour correspondant
      const stay = state.reservations.stays.find(
        (s) => s.id === lineData.stay_id
      );
      if (stay) {
        stay.food_lines.push(id);
        console.log(`🔗 [addFoodBookingLine] Ligne liée au stay ${stay.id}`);
      } else {
        console.warn(
          `⚠️ [addFoodBookingLine] Stay ${lineData.stay_id} introuvable`
        );
      }

      return id;
    },

    // Enrichir une ligne Food
    enrichFoodBookingLine(line) {
      console.log("🔧 [enrichFoodBookingLine] Ligne brute :", line);

      const food = state.products.list.find((f) => f.id === line.food_id);
      if (!food)
        console.warn(
          `⚠️ [enrichFoodBookingLine] Produit food ${line.food_id} introuvable`
        );

      const staySummary = (() => {
        const stay = state.reservations.stays.find(
          (s) => s.id === line.stay_id
        );
        if (!stay) {
          console.warn(
            `⚠️ [enrichFoodBookingLine] Stay ${line.stay_id} introuvable`
          );
          return null;
        }
        return {
          id: stay.id,
          room_id: stay.room_id,
          occupant_id: stay.occupant_id,
          status: stay.status,
        };
      })();

      const enriched = {
        ...line,
        food: food || null,
        stay_summary: staySummary,
      };
      console.log("✅ [enrichFoodBookingLine] Ligne enrichie :", enriched);

      return enriched;
    },

    //Ajouter une ligne Event
    addEventBookingLine(lineData) {
      console.log("🎟️ [addEventBookingLine] Données reçues :", lineData);

      const id = generateUniqueId();
      const total = lineData.qty * lineData.price_unit;

      const newLine = {
        id,
        stay_id: lineData.stay_id,
        event_id: lineData.event_id,
        ticket_id: lineData.ticket_id || null,
        description: lineData.description || "",
        qty: lineData.qty,
        price_unit: lineData.price_unit,
        event_price_total: total,
      };

      state.reservations.eventBookingLines.push(newLine);

      console.log("✅ [addEventBookingLine] Ligne brute ajoutée :", newLine);
      console.log(
        "📂 État actuel des eventBookingLines :",
        state.reservations.eventBookingLines
      );

      // Lier au stay
      const stay = state.reservations.stays.find(
        (s) => s.id === lineData.stay_id
      );
      if (stay) {
        stay.event_lines.push(id);
        console.log(`🔗 [addEventBookingLine] Ligne liée au stay ${stay.id}`);
      } else {
        console.warn(
          `⚠️ [addEventBookingLine] Stay ${lineData.stay_id} introuvable`
        );
      }

      return id;
    },

    // Enrichir une ligne Event
    enrichEventBookingLine(line) {
      console.log("🔧 [enrichEventBookingLine] Ligne brute :", line);

      const event = state.events.list.find((e) => e.id === line.event_id);
      if (!event)
        console.warn(
          `⚠️ [enrichEventBookingLine] Event ${line.event_id} introuvable`
        );

      const staySummary = (() => {
        const stay = state.reservations.stays.find(
          (s) => s.id === line.stay_id
        );
        if (!stay) {
          console.warn(
            `⚠️ [enrichEventBookingLine] Stay ${line.stay_id} introuvable`
          );
          return null;
        }
        return {
          id: stay.id,
          room_id: stay.room_id,
          occupant_id: stay.occupant_id,
          status: stay.status,
        };
      })();

      const enriched = {
        ...line,
        event: event || null,
        stay_summary: staySummary,
      };
      console.log("✅ [enrichEventBookingLine] Ligne enrichie :", enriched);

      return enriched;
    },

    //Ajouter une ligne Service
    addServiceBookingLine(lineData) {
      console.log("🛎️ [addServiceBookingLine] Données reçues :", lineData);

      const id = generateUniqueId();
      const total = lineData.qty * lineData.price_unit;

      const newLine = {
        id,
        stay_id: lineData.stay_id,
        service_id: lineData.service_id,
        description: lineData.description || "",
        qty: lineData.qty,
        price_unit: lineData.price_unit,
        service_price_total: total,
      };

      state.reservations.serviceBookingLines.push(newLine);

      console.log("✅ [addServiceBookingLine] Ligne brute ajoutée :", newLine);
      console.log(
        "📂 État actuel des serviceBookingLines :",
        state.reservations.serviceBookingLines
      );

      // Lier au stay
      const stay = state.reservations.stays.find(
        (s) => s.id === lineData.stay_id
      );
      if (stay) {
        stay.service_lines.push(id);
        console.log(`🔗 [addServiceBookingLine] Ligne liée au stay ${stay.id}`);
      } else {
        console.warn(
          `⚠️ [addServiceBookingLine] Stay ${lineData.stay_id} introuvable`
        );
      }

      return id;
    },

    // Enrichir une ligne Service
    enrichServiceBookingLine(line) {
      console.log("🔧 [enrichServiceBookingLine] Ligne brute :", line);

      const service = state.services.list.find((s) => s.id === line.service_id);
      if (!service)
        console.warn(
          `⚠️ [enrichServiceBookingLine] Service ${line.service_id} introuvable`
        );

      const staySummary = (() => {
        const stay = state.reservations.stays.find(
          (s) => s.id === line.stay_id
        );
        if (!stay) {
          console.warn(
            `⚠️ [enrichServiceBookingLine] Stay ${line.stay_id} introuvable`
          );
          return null;
        }
        return {
          id: stay.id,
          room_id: stay.room_id,
          occupant_id: stay.occupant_id,
          status: stay.status,
        };
      })();

      const enriched = {
        ...line,
        service: service || null,
        stay_summary: staySummary,
      };
      console.log("✅ [enrichServiceBookingLine] Ligne enrichie :", enriched);

      return enriched;
    },

    /**************************************Actions Police Forms********************************************************/
    // Créer une nouvelle police form liée à un stay
    addPoliceForm(stayId, formData = {}) {
      console.log("📝 [addPoliceForm] stayId:", stayId, "formData:", formData);
      const id = generateUniqueId();
      const stay = state.reservations.stays.find((s) => s.id === stayId);
      if (!stay) {
        console.error(`❌ [addPoliceForm] Stay ${stayId} introuvable`);
        return null;
      }

      // récupérer occupant pour préremplir si il existait déjà dans le stay
      let occupant = null;
      if (stay.occupant_id) {
        console.log("🔍 [addPoliceForm] Recherche de l'occupant...");
        occupant =
          state.clients.list.find((c) => c.id === stay.occupant_id) || null;
      }

      const now = new Date().toISOString();
      const newPoliceForm = {
        id,
        stay_id: stayId, // b
        occupant: [
          {
            first_name: occupant?.first_name || formData.first_name || "",
            last_name: occupant?.last_name || formData.last_name || "",
            nationality: formData.nationality || "",
            birthplace: formData.birthplace || "",
            address: formData.address || "",
            id_number: formData.id_number || "",
            id_issue_date: formData.id_issue_date || "",
            id_issue_place: formData.id_issue_place || "",
          },
        ],
        reason: formData.reason || "", // a
        transport: formData.transport || "", // a
        status: "draft", //b // `draft` par défaut, draft → validated → archived
        created_at: now, // b
        updated_at: now, // b
      };
      state.police_forms.police_forms.push(newPoliceForm);

      console.log("✅ [addPoliceForm] PoliceForm créée :", newPoliceForm);

      return id;
    },

    // Mettre à jour une police form existante
    updatePoliceForm(id, updatedData) {
      console.log("✏️ [updatePoliceForm] id:", id, "data:", updatedData);

      const index = state.police_forms.police_forms.findIndex(
        (p) => p.id === id
      );
      if (index === -1) {
        console.error(`❌ PoliceForm ${id} introuvable`);
        return null;
      }

      const existing = state.police_forms.police_forms[index];

      const updated = {
        ...existing,
        ...updatedData,
        occupant: updatedData.occupant || existing.occupant,
        updated_at: new Date().toISOString(),
      };

      state.police_forms.police_forms[index] = updated;

      console.log("✅ [updatePoliceForm] MAJ PoliceForm :", updated);

      return updated;
    },

    // Mettre à jour uniquement le statut (draft → validated, etc.) fonction à revoir si ici ou dans le store local
    updatePoliceFormStatus(id, newStatus) {
      console.log(`🔄 [updatePoliceFormStatus] ${id} → ${newStatus}`);

      const form = state.police_forms.police_formsfind((p) => p.id === id);
      if (!form) {
        console.error(`❌ PoliceForm ${id} introuvable`);
        return false;
      }

      form.status = newStatus;
      form.updated_at = new Date().toISOString();

      console.log(
        `✅ [updatePoliceFormStatus] ${id} est maintenant "${newStatus}"`
      );
      return true;
    },
  };
}

function createGetters(state) {
  return {
    // Client
    get selectedClient() {
      const list = state.clients.list;
      const selectedId = state.clients.selectedClientId;
      console.log("[GETTER] selectedClient ->", selectedId);
      return list.find((c) => c.id === selectedId) || null;
    },
    getClientById(id) {
      console.log("[GETTER] getClientById ->", id);
      return state.clients.list.find((client) => client.id === id);
    },
    getAllClients() {
      console.log("[GETTER] getAllClients");
      return state.clients.list;
    },
    get filteredList() {
      console.log("[GETTER] filteredList");
      const list = state.clients.list;
      const { searchText, membershipStatus, tierLevel } = state.clients.filters;
      let result = [...list];

      if (searchText) {
        const lower = searchText.toLowerCase();
        result = result.filter(
          (c) =>
            (c.name || "").toLowerCase().includes(lower) ||
            (c.email || "").toLowerCase().includes(lower) ||
            (c.phone || "").toLowerCase().includes(lower)
        );
      }
      if (membershipStatus) {
        result = result.filter((c) => c.membership_status === membershipStatus);
      }
      if (tierLevel) {
        result = result.filter((c) => c.tier_level === tierLevel);
      }

      return result;
    },

    // Food
    get selectedFood() {
      const list = state.products.list;
      const selectedId = state.products.selectedFoodId;
      console.log("[GETTER] selectedFood ->", selectedId);
      return list.find((f) => f.id === selectedId) || null;
    },
    getFoodById(id) {
      console.log("[GETTER] getFoodById ->", id);
      return state.products.list.find((f) => f.id === id);
    },
    getAllFood() {
      console.log("[GETTER] getAllFood");
      return state.products.list;
    },

    // Events
    get selectedEvent() {
      const list = state.events.list;
      const selectedId = state.events.selectedEventId;
      console.log("[GETTER] selectedEvent ->", selectedId);
      return list.find((e) => e.id === selectedId) || null;
    },
    getEventById(id) {
      console.log("[GETTER] getEventById ->", id);
      return state.events.list.find((e) => e.id === id);
    },
    getAllEvents() {
      console.log("[GETTER] getAllEvents");
      return state.events.list;
    },

    // Services
    get selectedService() {
      const list = state.services.list;
      const selectedId = state.services.selectedServiceId;
      console.log("[GETTER] selectedService ->", selectedId);
      return list.find((s) => s.id === selectedId) || null;
    },
    getServiceById(id) {
      console.log("[GETTER] getServiceById ->", id);
      return state.services.list.find((s) => s.id === id);
    },
    getAllServices() {
      console.log("[GETTER] getAllServices");
      return state.services.list;
    },

    /**************************************Getters Police Forms********************************************************/
    getPoliceFormById(id) {
      console.log("[GETTER] getPoliceFormById ->", id);
      return state.police_forms.police_forms.find((p) => p.id === id) || null;
    },

    getPoliceFormByStayId(stayId) {
      console.log("[GETTER] getPoliceFormByStayId ->", stayId);
      return (
        state.police_forms.police_forms.find((p) => p.stay_id === stayId) ||
        null
      );
    },

    getAllPoliceForms() {
      console.log("[GETTER] getAllPoliceForms");
      return state.police_forms.police_forms;
    },
  };
}

registry.category("services").add(SERVICE_NAME, {
  start() {
    const state = AppState;
    console.log("🧪 [STORE] AppState before reactive", state);

    const actions = createActions(state);
    console.log("🧪 [STORE] State and actions returned from store:", {
      state,
      actions,
    });
    const getters = createGetters(state);
    console.log("🧪 [STORE] Getters created:", getters);

    // On expose `state` (observable) + les actions et les getters
    return {
      state,
      actions: {
        ...actions,
      },
      getters: {
        ...getters,
      },
    };
  },
});
