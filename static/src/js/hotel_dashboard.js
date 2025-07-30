// File: hotel_dashboard/static/src/js/hotel_dashboard.js
odoo.define('hotel_dashboard.hotel_dashboard', function (require) {
    "use strict";

    var rpc = require('web.rpc');
    var core = require('web.core');
    var _t = core._t;

    // Shows modal with reservation form and handles edits
    class ReservationModal {
        constructor() {
            this.$modal = $('#reservation-modal');
            this.$overlay = this.$modal.find('.modal-overlay');
            this.$closeButtons = this.$modal.find('.modal-close, .modal-close-btn');
            this.$form = this.$modal.find('#reservation-form');

            this.bindEvents();
        }

        bindEvents() {
            var self = this;

            this.$closeButtons.on('click', function () {
                self.hide();
            });

            this.$overlay.on('click', function (ev) {
                if (ev.target === self.$overlay[0]) {
                    self.hide();
                }
            });

            this.$form.on('submit', function (ev) {
                ev.preventDefault();
                self.save();
            });
        }

        show(resv_id) {
            var self = this;
            rpc.query({
                route: '/hotel/dashboard/reservation/' + resv_id,
                params: {},
            }).then(function (result) {
                if(result.error) {
                    self._showError(result.error);
                    return;
                }
                self._fillForm(result);
                self.$modal.show();
                self.$modal.attr('aria-hidden', 'false');
                self.$form.find('input, select').first().focus();
            }).catch(function () {
                self._showError('Failed to load reservation');
            });
        }

        _fillForm(data) {
            this.$form.find('#resv-id').val(data.id);
            this.$form.find('#resv-code').val(data.name);
            this.$form.find('#resv-customer').val(data.customer_name);
            this.$form.find('#resv-status').val(data.status);
            this.$form.find('#resv-checkin').val(data.check_in_date);
            this.$form.find('#resv-checkout').val(data.check_out_date);
        }

        hide() {
            this.$modal.hide();
            this.$modal.attr('aria-hidden', 'true');
            this.$form[0].reset();
        }

        save() {
            var self = this;

            var vals = {
                id: this.$form.find('#resv-id').val(),
                status: this.$form.find('#resv-status').val(),
                check_in_date: this.$form.find('#resv-checkin').val(),
                check_out_date: this.$form.find('#resv-checkout').val(),
                customer_name: this.$form.find('#resv-customer').val(),
            };

            // Minimal validation
            if (!vals.check_in_date || !vals.check_out_date) {
                alert(_t("Check-in and Check-out dates are required"));
                return;
            }
            if (vals.check_out_date < vals.check_in_date) {
                alert(_t("Check-out date must be after Check-in date"));
                return;
            }

            rpc.query({
                route: '/hotel/dashboard/update_reservation',
                params: vals,
            }).then(function(response) {
                if(response.success) {
                    self.hide();
                    self._triggerRefresh();
                } else if (response.error) {
                    alert(_t('Error: ') + response.error);
                }
            }).catch(function(err){
                alert(_t("Failed to save reservation"));
            });
        }

        _triggerRefresh() {
            $(document).trigger('hotel_dashboard:refresh');
        }

        _showError(message) {
            alert(message);
        }
    }

    class HotelDashboard {
        constructor() {
            this.today = moment().startOf('day');
            this.currentMonth = this.today.clone().startOf('month');

            this.filterStatus = 'all';

            this.$kpiTotalConfirmed = $('#kpi-total-confirmed > div:first-child');
            this.$kpiTotalCheckout = $('#kpi-total-checkout > div:first-child');
            this.$kpiTodayAvailability = $('#kpi-today-availability > div:first-child');
            this.$kpiTotalReservations = $('#kpi-total-reservations > div:first-child');

            this.$statusButtons = $('.status-filter-button');
            this.$calendarLeft = $('.calendar-left-column');
            this.$calendarMain = $('.calendar-main');

            this.$monthLabel = $('#calendar-current-month');

            this.reservationModal = new ReservationModal();

            this.bindEvents();
            this.loadData();
        }

        bindEvents() {
            var self = this;

            this.$statusButtons.on('click', function () {
                var status = $(this).data('status');
                self.filterStatus = status;
                self.$statusButtons.removeClass('active');
                $(this).addClass('active');
                self.loadData();
            });

            // Default: activate 'ALL'
            this.$statusButtons.filter('[data-status="all"]').addClass('active');

            $('.calendar-button[data-action]').on('click', function () {
                var action = $(this).data('action');
                if (action === 'today') {
                    self.currentMonth = self.today.clone().startOf('month');
                } else if (action === 'prev-month') {
                    self.currentMonth = self.currentMonth.clone().subtract(1, 'month');
                } else if (action === 'next-month') {
                    self.currentMonth = self.currentMonth.clone().add(1, 'month');
                }
                self.loadData();
            });

            this.$calendarMain.on('click', '.calendar-row-cell.calendar-clickable', function () {
                var resvId = $(this).data('resv-id');
                if (resvId) {
                    self.reservationModal.show(resvId);
                }
            });

            // Refresh after save
            $(document).on('hotel_dashboard:refresh', function () {
                self.loadData();
            });
        }

        loadData() {
            var self = this;

            var start = self.currentMonth.clone().startOf('month').format('YYYY-MM-DD');
            var end = self.currentMonth.clone().endOf('month').format('YYYY-MM-DD');

            rpc.query({
                route: '/hotel/dashboard/data',
                params: {
                    start: start,
                    end: end,
                    filter_status: this.filterStatus,
                }
            }).then(function(data) {
                self._renderKpis(data.kpi);
                self._renderCalendar(data.room_types, data.reservations, data.rooms_maintenance_cleaning);
                self._renderMonthLabel(self.currentMonth);
            });
        }

        _renderKpis(kpi) {
            this.$kpiTotalConfirmed.text(kpi.total_confirmed);
            this.$kpiTotalCheckout.text(kpi.total_checkout);
            this.$kpiTodayAvailability.text(kpi.today_availability);
            this.$kpiTotalReservations.text(kpi.total_reservations);
        }

        _renderMonthLabel(monthMoment) {
            this.$monthLabel.text(monthMoment.format('MMMM YYYY'));
        }

        _renderCalendar(roomTypes, reservations, roomsMaintenanceCleaning) {
            var self = this;

            // Left column: room types and rooms
            this.$calendarLeft.empty();
            var totalRows = 0;
            for (let rt of roomTypes) {
                var $rtHeader = $('<div role="row" class="room-type-header" tabindex="-1"></div>');
                $rtHeader.text(rt.name);
                this.$calendarLeft.append($rtHeader);
                totalRows++;

                for (let room of rt.rooms) {
                    var $roomCell = $('<div role="row" class="room-name-cell" tabindex="-1"></div>');
                    $roomCell.text(room.name);
                    $roomCell.attr('data-room-id', room.id);
                    this.$calendarLeft.append($roomCell);
                    totalRows++;
                }
            }
            this.$calendarLeft.attr('aria-rowcount', totalRows);

            // Right calendar header: days of the month
            this.$calendarMain.empty();

            var daysInMonth = self.currentMonth.daysInMonth();
            var $headerRow = $('<div role="row" class="calendar-header"></div>');
            // Space for left empty column header
            var $emptyHead = $('<div class="calendar-header-cell left-column" aria-hidden="true"></div>');
            $headerRow.append($emptyHead);

            for (var d = 1; d <= daysInMonth; d++) {
                var day = self.currentMonth.clone().date(d);
                var dayName = day.format('dd'); // Mo, Tu, etc.
                var dayNum = d;
                var $dayHeader = $('<div role="columnheader" class="calendar-header-cell"></div>').attr('title', day.format('dddd'));
                $dayHeader.html(dayName + '<br/>' + dayNum);
                $headerRow.append($dayHeader);
            }
            this.$calendarMain.append($headerRow);

            // Build lookup: reservations by room and date
            var reservationsByRoomId = {};
            for (let resv of reservations) {
                if (!reservationsByRoomId[resv.room_id]) {
                    reservationsByRoomId[resv.room_id] = [];
                }
                reservationsByRoomId[resv.room_id].push(resv);
            }
            // Maintenance/cleaning by room id
            var roomStatusById = {};
            for(let rmc of roomsMaintenanceCleaning){
                roomStatusById[rmc.room_id] = rmc;
            }

            // For each room, construct a row
            for (let rt of roomTypes) {
                // Room type header row filler in main grid
                var $rtHeaderRow = $('<div role="row" aria-rowspan="' + (rt.rooms.length || 1) + '" class="calendar-row"></div>');
                // This empty cell aligns with left column room type header
                var $emptyRight = $('<div class="calendar-row-cell left-column" aria-hidden="true"></div>');
                $rtHeaderRow.append($emptyRight);
                // Add empty cells for days (empty to align visually)
                for (var d = 1; d <= daysInMonth; d++) {
                    var $emptyCell = $('<div class="calendar-row-cell" aria-hidden="true">&nbsp;</div>');
                    $rtHeaderRow.append($emptyCell);
                }
                this.$calendarMain.append($rtHeaderRow);

                for (let room of rt.rooms) {
                    var $row = $('<div role="row" class="calendar-row"></div>');
                    var $roomLabelCell = $('<div role="rowheader" class="calendar-row-cell left-column"></div>').text(room.name);
                    $row.append($roomLabelCell);

                    // For each day cell, we check state and render with color, text etc.
                    for (var d = 1; d <= daysInMonth; d++) {
                        var cellDate = self.currentMonth.clone().date(d).format('YYYY-MM-DD');

                        // Determine cell status in priority:
                        // Maintenance/Cleaning on room itself > Reservation > Available

                        var statusClass = 'calendar-cell-available';
                        var cellText = '';

                        if (roomStatusById[room.id]) {
                            // Room is under cleaning or maintenance full month? Assume status applies to all dates.
                            statusClass = 'calendar-cell-maintenance';
                            if (roomStatusById[room.id].status === 'maintenance') {
                                cellText = 'Maint.';
                            } else if (roomStatusById[room.id].status === 'cleaning') {
                                cellText = 'Clean.';
                            }
                        } else if (reservationsByRoomId[room.id]) {
                            // Check if this date is within any reservation for this room
                            var resvHere = null;
                            for (let resv of reservationsByRoomId[room.id]) {
                                var inRange = (cellDate >= resv.check_in_date) && (cellDate < resv.check_out_date);
                                if(inRange) {
                                    resvHere = resv;
                                    break;
                                }
                            }
                            if (resvHere) {
                                // Determine color and text by status
                                switch(resvHere.status) {
                                    case 'booking':
                                        statusClass = 'calendar-cell-reserved';
                                        cellText = resvHere.name;
                                        break;
                                    case 'confirmed':
                                        statusClass = 'calendar-cell-reserved';
                                        cellText = resvHere.name;
                                        break;
                                    case 'checked_in':
                                        statusClass = 'calendar-cell-occupied';
                                        cellText = resvHere.customer_name || resvHere.name;
                                        break;
                                    case 'checkout':
                                        statusClass = 'calendar-cell-checkout';
                                        cellText = resvHere.name;
                                        break;
                                    case 'cleaning':
                                    case 'maintenance':
                                        statusClass = 'calendar-cell-maintenance';
                                        cellText = resvHere.status === 'maintenance' ? 'Maint.' : 'Clean.';
                                        break;
                                    default:
                                        statusClass = 'calendar-cell-reserved';
                                        cellText = resvHere.name;
                                }
                            }
                        }

                        var $cell = $('<div tabindex="0" role="gridcell" class="calendar-row-cell"></div>');
                        $cell.addClass(statusClass);
                        if (cellText) {
                            $cell.text(cellText);
                        }

                        // If cell corresponds to a reservation, add clickability
                        if (typeof resvHere === 'object' && resvHere !== null) {
                            $cell.addClass('calendar-clickable');
                            $cell.attr('data-resv-id', resvHere.id);
                            $cell.attr('title', cellText + ' (' + resvHere.status.replace('_', ' ') + ')');
                        } else {
                            $cell.attr('title', 'Available');
                        }

                        // Highlight today cell column
                        if (cellDate === self.today.format('YYYY-MM-DD')) {
                            $cell.css('outline', '1px solid #3a7bd5');
                        }

                        $row.append($cell);
                    }

                    this.$calendarMain.append($row);
                }
            }
            this.$calendarMain.attr('aria-rowcount', totalRows + 1);
            this.$calendarMain.attr('aria-colcount', daysInMonth + 1);
        }
    }

    $(document).ready(function () {
        // Load momentjs from Odoo core if needed
        if (window.moment === undefined) {
            // Load moment js dynamically
            throw new Error('MomentJS must be available for hotel dashboard to work.');
        }
        new HotelDashboard();
    });

});