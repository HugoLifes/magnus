import 'package:flutter/widgets.dart';

import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';
import '../../domain/entities.dart';

/// Tabla de la matriz de cuantizaciones (usa el Table de flutter/widgets, sin
/// dependencia de Material, para funcionar dentro de cualquier shell).
class QuantMatrixTable extends StatelessWidget {
  const QuantMatrixTable({super.key, required this.rows});
  final List<Compatibility> rows;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      padding: EdgeInsets.zero,
      child: Table(
        columnWidths: const {
          0: FixedColumnWidth(78),
          1: FlexColumnWidth(),
          2: FixedColumnWidth(86),
          3: FixedColumnWidth(86),
          4: FixedColumnWidth(64),
          5: FlexColumnWidth(),
        },
        defaultVerticalAlignment: TableCellVerticalAlignment.middle,
        children: [
          _header(t),
          for (final r in rows) _row(t, r),
        ],
      ),
    );
  }

  TableRow _header(MagnusTheme t) => TableRow(
        decoration: BoxDecoration(color: t.surfaceAlt),
        children: [
          _Cell('Cuant', t, header: true),
          _Cell('VRAM req.', t, header: true),
          _Cell('% destino', t, header: true),
          _Cell('Margen', t, header: true),
          _Cell('¿Entra?', t, header: true),
          _Cell('Runtimes', t, header: true),
        ],
      );

  TableRow _row(MagnusTheme t, Compatibility r) {
    final pct = r.utilizationPct;
    final pctColor = pct > 95 ? t.bad : (pct > 80 ? t.warn : t.textMuted);
    return TableRow(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: t.stroke)),
      ),
      children: [
        _Cell(r.quant, t, strong: true),
        _Cell('${r.requiredGib.toStringAsFixed(1)} GiB', t),
        _Cell('${pct.toStringAsFixed(0)}%', t, color: pctColor),
        _Cell('${r.headroomGib.toStringAsFixed(1)} GiB', t),
        _Verdict(r.fits, t),
        _Cell(r.runtimes.isEmpty ? '—' : r.runtimes.join(', '), t),
      ],
    );
  }
}

class _Cell extends StatelessWidget {
  const _Cell(this.text, this.t,
      {this.header = false, this.strong = false, this.color});
  final String text;
  final MagnusTheme t;
  final bool header;
  final bool strong;
  final Color? color;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
        child: Text(
          text,
          style: header
              ? t.small.copyWith(fontWeight: FontWeight.w700, color: t.textMuted)
              : t.body.copyWith(
                  color: color ?? t.text,
                  fontWeight: strong ? FontWeight.w700 : FontWeight.w400),
        ),
      );
}

class _Verdict extends StatelessWidget {
  const _Verdict(this.fits, this.t);
  final bool fits;
  final MagnusTheme t;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        child: Align(
          alignment: Alignment.centerLeft,
          child: Pill(fits ? 'sí' : 'no', color: fits ? t.ok : t.bad),
        ),
      );
}
