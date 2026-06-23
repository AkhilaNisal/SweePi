import 'package:flutter_test/flutter_test.dart';
import 'package:sweepi/features/app/app_controller.dart';
import 'package:sweepi/main.dart';

void main() {
  testWidgets('App shell renders', (tester) async {
    await tester.pumpWidget(SweePiApp(controller: AppController()));

    expect(find.text('SweePi'), findsOneWidget);
  });
}
