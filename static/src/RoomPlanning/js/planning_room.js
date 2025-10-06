/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class RoomPlanning extends Component {
    static template = "rooms_planning.template";

    setup() {
        this.state = useState({
            currentDate: new Date(),
            viewDays: 7
        });

        // 10 chambres A001 à A010
        this.rooms = Array.from({ length: 10 }, (_, i) => ({
            id: i + 1,
            name: `A${String(i + 1).padStart(3, '0')}`
        }));

        this.dates = this.generateDates();
        this.activities = this.generateMockActivities();
    }

    generateDates() {
        const dates = [];
        const start = new Date(this.state.currentDate);
        
        for (let i = 0; i < this.state.viewDays; i++) {
            const date = new Date(start);
            date.setDate(start.getDate() + i);
            dates.push({
                full: date,
                iso: date.toISOString().split('T')[0],
                display: `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}`,
                dayName: ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'][date.getDay()]
            });
        }
        return dates;
    }

    generateMockActivities() {
        const activities = [];
        let id = 1;

        // Pour chaque chambre, générer des activités réalistes
        this.rooms.forEach((room, roomIdx) => {
            const startDate = new Date(this.state.currentDate);
            
            // Pattern aléatoire mais réaliste
            if (roomIdx % 3 === 0) {
                // Chambre avec réservation longue
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'booking',
                    start: this.formatDateTime(startDate, 14, 0),
                    end: this.formatDateTime(this.addDays(startDate, 3), 11, 0),
                    status: 'in_stay',
                    guest: `Client ${roomIdx + 1}`,
                    color: '#4caf50'
                });

                // Nettoyage après
                const cleanDate = this.addDays(startDate, 3);
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'cleaning',
                    start: this.formatDateTime(cleanDate, 11, 0),
                    end: this.formatDateTime(cleanDate, 12, 30),
                    status: 'cleaning',
                    guest: 'Nettoyage',
                    color: '#ff9800'
                });

            } else if (roomIdx % 3 === 1) {
                // Maintenance puis réservations courtes
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'maintenance',
                    start: this.formatDateTime(startDate, 8, 0),
                    end: this.formatDateTime(this.addDays(startDate, 1), 18, 0),
                    status: 'maintenance',
                    guest: 'Réparation',
                    color: '#f44336'
                });

                // Day-use après maintenance
                const dayUseDate = this.addDays(startDate, 2);
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'day_use',
                    start: this.formatDateTime(dayUseDate, 10, 0),
                    end: this.formatDateTime(dayUseDate, 14, 30),
                    status: 'confirmed',
                    guest: 'Location 4h30',
                    color: '#2196F3'
                });

                // Réservation classique
                const bookDate = this.addDays(startDate, 4);
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'booking',
                    start: this.formatDateTime(bookDate, 15, 0),
                    end: this.formatDateTime(this.addDays(bookDate, 2), 11, 0),
                    status: 'confirmed',
                    guest: `M. Dupont ${roomIdx}`,
                    color: '#4caf50'
                });

            } else {
                // Pattern mixte
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'booking',
                    start: this.formatDateTime(startDate, 16, 0),
                    end: this.formatDateTime(this.addDays(startDate, 1), 11, 0),
                    status: 'confirmed',
                    guest: `Famille ${roomIdx}`,
                    color: '#4caf50'
                });

                const clean1 = this.addDays(startDate, 1);
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'cleaning',
                    start: this.formatDateTime(clean1, 11, 0),
                    end: this.formatDateTime(clean1, 12, 0),
                    status: 'cleaning',
                    guest: 'Nettoyage',
                    color: '#ff9800'
                });

                // Day-use
                const dayUse = this.addDays(startDate, 2);
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'day_use',
                    start: this.formatDateTime(dayUse, 12, 30),
                    end: this.formatDateTime(dayUse, 16, 0),
                    status: 'confirmed',
                    guest: 'Location 3h30',
                    color: '#2196F3'
                });

                // Réservation longue
                const longStay = this.addDays(startDate, 3);
                activities.push({
                    id: id++,
                    room_id: room.id,
                    type: 'booking',
                    start: this.formatDateTime(longStay, 14, 0),
                    end: this.formatDateTime(this.addDays(longStay, 3), 11, 0),
                    status: 'confirmed',
                    guest: `Client VIP ${roomIdx}`,
                    color: '#4caf50'
                });
            }
        });

        return activities;
    }

    // Utilitaires
    addDays(date, days) {
        const result = new Date(date);
        result.setDate(result.getDate() + days);
        return result;
    }

    formatDateTime(date, hour, minute) {
        const d = new Date(date);
        d.setHours(hour, minute, 0, 0);
        return d.toISOString();
    }

    // Calcul de position pour un bloc
    calculateBlockPosition(activity, dateStr) {
        const start = new Date(activity.start);
        const end = new Date(activity.end);
        const currentDate = new Date(dateStr);
        
        const dayStart = new Date(currentDate);
        dayStart.setHours(0, 0, 0, 0);
        
        const dayEnd = new Date(currentDate);
        dayEnd.setHours(23, 59, 59, 999);

        if (end < dayStart || start > dayEnd) {
            return null;
        }

        const effectiveStart = start < dayStart ? dayStart : start;
        const effectiveEnd = end > dayEnd ? dayEnd : end;

        const startHour = effectiveStart.getHours();
        const startMinute = effectiveStart.getMinutes();
        const endHour = effectiveEnd.getHours();
        const endMinute = effectiveEnd.getMinutes();

        const startFraction = (startHour + startMinute / 60) / 24;
        const endFraction = (endHour + endMinute / 60) / 24;
        const widthFraction = endFraction === 0 && end > dayEnd ? 1 - startFraction : endFraction - startFraction;

        return {
            left: startFraction * 100,
            width: widthFraction * 100,
            label: activity.guest,
            type: activity.type,
            color: activity.color,
            startTime: `${startHour.toString().padStart(2, '0')}:${startMinute.toString().padStart(2, '0')}`,
            endTime: `${endHour.toString().padStart(2, '0')}:${endMinute.toString().padStart(2, '0')}`
        };
    }

    getBlocksForRoomAndDate(roomId, dateStr) {
        return this.activities
            .filter(a => a.room_id === roomId)
            .map(activity => this.calculateBlockPosition(activity, dateStr))
            .filter(block => block !== null);
    }

    getTypeIcon(type) {
        const icons = {
            'booking': '🛏️',
            'cleaning': '🧹',
            'maintenance': '🔧',
            'day_use': '⏱️'
        };
        return icons[type] || '📋';
    }

    // Navigation
    previousWeek() {
        const newDate = new Date(this.state.currentDate);
        newDate.setDate(newDate.getDate() - 7);
        this.state.currentDate = newDate;
        this.dates = this.generateDates();
        this.activities = this.generateMockActivities();
    }

    nextWeek() {
        const newDate = new Date(this.state.currentDate);
        newDate.setDate(newDate.getDate() + 7);
        this.state.currentDate = newDate;
        this.dates = this.generateDates();
        this.activities = this.generateMockActivities();
    }

    today() {
        this.state.currentDate = new Date();
        this.dates = this.generateDates();
        this.activities = this.generateMockActivities();
    }

    onBlockClick(activity) {
        console.log('Clicked activity:', activity);
        // Ouvrir un modal ou un formulaire Odoo
    }
}

registry.category("actions").add("room_planning.app", RoomPlanning);

console.log("✅ RoomPlanning avec précision horaire enregistré !");