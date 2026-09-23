/// Formatos de cifras del medidor. Los costes por respuesta son de fracciones de
/// centavo: con dos decimales todo saldría "$0.00" y el ahorro no se vería.
String formatUsd(double value) {
  final abs = value.abs();
  final sign = value < 0 ? '-' : '';
  if (abs >= 1) return '$sign\$${abs.toStringAsFixed(2)}';
  if (abs >= 0.01) return '$sign\$${abs.toStringAsFixed(3)}';
  if (abs == 0) return r'$0';
  return '$sign\$${abs.toStringAsFixed(6)}';
}

String formatNum(double? value, {int decimals = 1, String unit = ''}) =>
    value == null ? '—' : '${value.toStringAsFixed(decimals)}$unit';

String formatGib(double? value) => formatNum(value, decimals: 1, unit: ' GiB');

String formatBytes(int? bytes) {
  if (bytes == null) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  var v = bytes.toDouble();
  var i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return '${v.toStringAsFixed(i == 0 ? 0 : 1)} ${units[i]}';
}
