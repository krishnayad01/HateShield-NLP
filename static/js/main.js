/* main.js – global UI helpers for HateShield */

// Auto-dismiss flash alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(function () {
    if (typeof bootstrap === 'undefined' || !bootstrap.Alert) return;
    document.querySelectorAll('.alert.alert-dismissible').forEach(function (el) {
      var bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    });
  }, 5000);
});
