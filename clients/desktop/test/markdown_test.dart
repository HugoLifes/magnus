import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:magnus_desktop/core/theme/design_system.dart';
import 'package:magnus_desktop/core/theme/magnus_theme.dart';
import 'package:magnus_desktop/shared/widgets/markdown.dart';

/// Envuelve el widget con lo mínimo que necesita: tokens del tema y direccionalidad.
Widget _conTema(Widget child) => Directionality(
      textDirection: TextDirection.ltr,
      child: MagnusTheme.forDesign(DesignSystem.windows, Brightness.dark)
          .provide(child: MediaQuery(data: const MediaQueryData(), child: child)),
    );

void main() {
  testWidgets('un párrafo normal se muestra tal cual', (tester) async {
    await tester.pumpWidget(_conTema(const MarkdownText('Hola, soy Magnus.')));
    expect(find.textContaining('Hola, soy Magnus.'), findsOneWidget);
  });

  testWidgets('las viñetas salen como lista', (tester) async {
    await tester.pumpWidget(_conTema(const MarkdownText('- uno\n- dos')));
    expect(find.text('•'), findsNWidgets(2));
    expect(find.textContaining('uno'), findsOneWidget);
    expect(find.textContaining('dos'), findsOneWidget);
  });

  testWidgets('las listas numeradas conservan su número', (tester) async {
    await tester.pumpWidget(_conTema(const MarkdownText('1. primero\n2. segundo')));
    expect(find.text('1.'), findsOneWidget);
    expect(find.text('2.'), findsOneWidget);
  });

  testWidgets('un bloque de código trae su lenguaje y el botón de copiar', (tester) async {
    await tester.pumpWidget(_conTema(
      const MarkdownText('Mira:\n```python\nprint("hola")\n```'),
    ));
    expect(find.text('python'), findsOneWidget);
    expect(find.text('copiar'), findsOneWidget);
    expect(find.textContaining('print("hola")'), findsOneWidget);
  });

  testWidgets('un bloque a medio escribir también se pinta', (tester) async {
    // Mientras el modelo responde, el cierre ``` todavía no ha llegado.
    await tester.pumpWidget(_conTema(const MarkdownText('```dart\nvoid main() {')));
    expect(find.text('dart'), findsOneWidget);
    expect(find.textContaining('void main()'), findsOneWidget);
  });

  testWidgets('los títulos no se quedan con las almohadillas', (tester) async {
    await tester.pumpWidget(_conTema(const MarkdownText('## Resumen\ncontenido')));
    expect(find.textContaining('Resumen'), findsOneWidget);
    expect(find.textContaining('##'), findsNothing);
  });

  testWidgets('negritas y código en línea no dejan los símbolos a la vista', (tester) async {
    await tester.pumpWidget(_conTema(const MarkdownText('Usa **negrita** y `codigo`.')));
    expect(find.textContaining('**'), findsNothing);
    expect(find.textContaining('`'), findsNothing);
    expect(find.textContaining('negrita'), findsOneWidget);
  });

  testWidgets('un texto vacío no revienta', (tester) async {
    await tester.pumpWidget(_conTema(const MarkdownText('')));
    expect(find.byType(MarkdownText), findsOneWidget);
  });
}
