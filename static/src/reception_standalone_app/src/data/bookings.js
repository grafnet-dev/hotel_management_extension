import { roomTypes } from './rooms.js';
import { clients } from './clients.js';
import { foodBookingLines } from './food_booking_lines.js';
import { eventBookingLines } from './event_booking_lines.js';
import { serviceBookingLines } from './service_booking_lines.js';

// Utilitaires
function getClientById(id) {
  return clients.find(c => c.id === id);
}

function getRoomDetails(roomId) {
  const room = roomTypes.flatMap(rt => rt.rooms).find(r => r.id === roomId);
  if (!room) return null;
  const roomType = roomTypes.find(rt => rt.rooms.some(r => r.id === roomId));
  return {
    room_id: room.id,
    room_name: room.name,
    room_type: roomType?.name || "",
    price_per_night: roomType?.price_per_night || 0,
    hourly_rate: roomType?.hourly_rate || 0,
    day_use_price: roomType?.day_use_price || 0,
    default_check_in_time: roomType?.default_check_in_time || 14.0,
    default_check_out_time: roomType?.default_check_out_time || 12.0,
    image: room.room_imagestypes?.[0]?.image || null,
    status: room.status,
    is_available: room.is_available,
  };
}

function getLinesForStay(lines, stayId) {
  return lines.filter(l => l.stay_id === stayId);
}

function logStayConsumptions(stay) {
  const { id, occupant_name, food_booking_lines, event_booking_lines, service_booking_lines, room_price_total, consumption_total, total_amount } = stay;

  const foodTotal = food_booking_lines.reduce((sum, l) => sum + l.total_price, 0);
  const eventTotal = event_booking_lines.reduce((sum, l) => sum + l.total_price, 0);
  const serviceTotal = service_booking_lines.reduce((sum, l) => sum + l.total_price, 0);

  console.log(`\n📋 Résumé de consommation pour le séjour ID ${id} – Occupant : ${occupant_name}`);
  console.table([
    { Type: "Chambre", Montant: `${room_price_total.toLocaleString()} FCFA` },
    { Type: "Consommation (nourriture)", Montant: `${foodTotal.toLocaleString()} FCFA` },
    { Type: "Consommation (événements)", Montant: `${eventTotal.toLocaleString()} FCFA` },
    { Type: "Consommation (services)", Montant: `${serviceTotal.toLocaleString()} FCFA` },
    { Type: "TOTAL consommation", Montant: `${consumption_total.toLocaleString()} FCFA` },
    { Type: "TOTAL général", Montant: `${total_amount.toLocaleString()} FCFA` },
  ]);
}

function calculateStayPrice(stay, roomDetails) {
  const checkin = new Date(stay.checkin_date);
  const checkout = new Date(stay.checkout_date);
  const msInHour = 1000 * 60 * 60;
  const msInDay = msInHour * 24;

  let basePrice = 0;
  let earlyExtra = 0;
  let lateExtra = 0;

  const durationMs = checkout - checkin;
  const durationHours = durationMs / msInHour;
  const durationDays = Math.ceil(durationMs / msInDay);

  if (stay.reservation_type === 'overnight') {
    basePrice = durationDays * roomDetails.price_per_night;
  } else if (stay.reservation_type === 'day_use') {
    basePrice = roomDetails.day_use_price;
  } else if (stay.reservation_type === 'flexible') {
    basePrice = Math.ceil(durationHours) * roomDetails.hourly_rate;
  }

  if (stay.early_checkin_requested && stay.early_checkin_hour != null) {
    const earlyHours = Math.max(0, roomDetails.default_check_in_time - stay.early_checkin_hour);
    earlyExtra = earlyHours * roomDetails.hourly_rate;
  }

  if (stay.late_checkout_requested && stay.late_checkout_hour != null) {
    const lateHours = Math.max(0, stay.late_checkout_hour - roomDetails.default_check_out_time);
    lateExtra = lateHours * roomDetails.hourly_rate;
  }

  const total = basePrice + earlyExtra + lateExtra;
  console.table({
    stay_id: stay.id,
    occupant: stay.occupant_name,
    reservation_type: stay.reservation_type,
    basePrice,
    earlyExtra,
    lateExtra,
    total
  });

  return total;
}

function calculateTotals(stay) {
  const food = stay.food_booking_lines.reduce((sum, l) => sum + l.total_price, 0);
  const events = stay.event_booking_lines.reduce((sum, l) => sum + l.total_price, 0);
  const services = stay.service_booking_lines.reduce((sum, l) => sum + l.total_price, 0);
  const consumption = food + events + services;
  const room = stay.price;
  return {
    room_price_total: room,
    consumption_total: consumption,
    total_amount: room + consumption
  };
}

function getReservationsForRoom(roomId) {
  return roomBookingList.flatMap(b => b.stays).filter(s => s.room_id === roomId);
}

// Données principales
export const roomBookingList = [
  {
    id: 4,
    group_code: "LASTMIN20250801",
    booking_date: "2025-08-01",
    status: "confirmed",
    client: getClientById(104),
    stays: [
      {
        id: 205,
        occupant_name: "Laura",
        room_id: 103,
        reservation_type: "overnight",
        checkin_date: "2025-08-01T23:45:00",
        checkout_date: "2025-08-02T11:00:00",
        status: "checked_out",
        early_checkin_requested: false,
        late_checkout_requested: false,
        was_requalified_flexible: true,
        extra_night_required: false,
        notes: "Réservation de dernière minute après vol retardé.",
        food_booking_lines: [],
        event_booking_lines: [],
        service_booking_lines: []
      }
    ]
  },
  {
    id: 5,
    group_code: "CORPOCONF20250810",
    booking_date: "2025-07-25",
    status: "confirmed",
    client: getClientById(105),
    stays: [
      {
        id: 206,
        occupant_name: "Mikael ",
        room_id: 104,
        reservation_type: "overnight",
        checkin_date: "2025-08-10T07:00:00",
        checkout_date: "2025-08-13T11:00:00",
        status: "confirmed",
        early_checkin_requested: true,
        early_checkin_hour: 7.0,
        late_checkout_requested: false,
        was_requalified_flexible: true,
        extra_night_required: false,
        notes: "Séjour prolongé pour assister à une conférence sur le numérique.",
        food_booking_lines: [],
        event_booking_lines: [],
        service_booking_lines: []
      },
      {
        id: 207,
        occupant_name: "Sèdjro",
        room_id: 105,
        reservation_type: "flexible",
        checkin_date: "2025-08-10T14:00:00",
        checkout_date: "2025-08-14T18:00:00",
        status: "planned",
        early_checkin_requested: false,
        late_checkout_requested: true,
        late_checkout_hour: 18.0,
        was_requalified_flexible: false,
        extra_night_required: true,
        notes: "Arrivée pour salon professionnel avec late-checkout négocié.",
        food_booking_lines: [],
        event_booking_lines: [],
        service_booking_lines: []
      }
    ]
  },
  {
    id: 6,
    group_code: "FAMTRIP20250805",
    booking_date: "2025-07-10",
    status: "confirmed",
    client: getClientById(106),
    stays: [
      {
        id: 208,
        occupant_name: "Michel Zinsou",
        room_id: 106,
        reservation_type: "overnight",
        checkin_date: "2025-08-05T15:00:00",
        checkout_date: "2025-08-08T11:00:00",
        status: "confirmed",
        early_checkin_requested: false,
        late_checkout_requested: false,
        was_requalified_flexible: false,
        extra_night_required: false,
        notes: "Voyage familial d’été. Deux enfants.",
        food_booking_lines: [],
        event_booking_lines: [],
        service_booking_lines: []
      },
      {
        id: 209,
        occupant_name: "Sedo  Zinsou",
        room_id: 107,
        reservation_type: "overnight",
        checkin_date: "2025-08-05T15:00:00",
        checkout_date: "2025-08-08T11:00:00",
        status: "confirmed",
        early_checkin_requested: false,
        late_checkout_requested: false,
        was_requalified_flexible: false,
        extra_night_required: false,
        notes: "Chambre séparée pour les parents.",
        food_booking_lines: [],
        event_booking_lines: [],
        service_booking_lines: []
      }
    ]
  },
  {
    id: 7,
    group_code: "MIDSTAY20250728",
    booking_date: "2025-07-21",
    status: "in_progress",
    client: getClientById(107),
    stays: [
      {
        id: 210,
        occupant_name: "Simon Edo",
        room_id: 108,
        reservation_type: "overnight",
        checkin_date: "2025-07-28T13:30:00",
        checkout_date: "2025-08-03T11:00:00",
        status: "checked_in",
        early_checkin_requested: false,
        late_checkout_requested: true,
        late_checkout_hour: 15.5,
        was_requalified_flexible: true,
        extra_night_required: true,
        notes: "Demande prolongation pour visite touristique.",
        food_booking_lines: [],
        event_booking_lines: [],
        service_booking_lines: []
      }
    ]
  }
];

// Injection des consommations, chambres, prix et totaux
roomBookingList.forEach(booking => {
  booking.stays = booking.stays.map(stay => {
    const details = getRoomDetails(stay.room_id);
    const foodLines = getLinesForStay(foodBookingLines, stay.id);
    const eventLines = getLinesForStay(eventBookingLines, stay.id);
    const serviceLines = getLinesForStay(serviceBookingLines, stay.id);
    const price = calculateStayPrice(stay, details);

    const enrichedStay = {
      ...stay,
      room_id: details.room_id,
      room_name: details.room_name,
      room_type: details.room_type,
      room_details: details,
      price,
      food_booking_lines: foodLines,
      event_booking_lines: eventLines,
      service_booking_lines: serviceLines,
      ...calculateTotals({
        ...stay,
        price,
        food_booking_lines: foodLines,
        event_booking_lines: eventLines,
        service_booking_lines: serviceLines
      })
    };

    logStayConsumptions(enrichedStay);
    return enrichedStay;
  });

  booking.total_booking_amount = booking.stays.reduce((sum, stay) => sum + stay.total_amount, 0);
});
