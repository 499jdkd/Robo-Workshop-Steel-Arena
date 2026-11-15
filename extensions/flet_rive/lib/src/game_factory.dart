import 'dart:math' as math;
import 'package:flet/flet.dart';
import 'package:flutter/material.dart';

/// Presentation only: inventory is committed by Python before receipt changes.
class GameFactoryControl extends StatefulWidget {
  const GameFactoryControl({super.key,required this.control});
  final Control control;
  @override
  State<GameFactoryControl> createState()=>_GameFactoryControlState();
}
class _GameFactoryControlState extends State<GameFactoryControl> with SingleTickerProviderStateMixin {
  late final AnimationController motor=AnimationController(vsync:this,duration:const Duration(seconds:12))..repeat();
  final watch=Stopwatch();
  String receipt='';
  @override
  Widget build(BuildContext context) {
    final next=widget.control.getString('receipt','')!;
    if(next!=receipt){receipt=next;watch..reset()..start();}
    return LayoutControl(control:widget.control,child:RepaintBoundary(child:AnimatedBuilder(
      animation:motor,builder:(context,_)=>CustomPaint(painter:_FactoryPainter(motor.value*12,receipt.isEmpty?-1:watch.elapsedMilliseconds/1000),size:Size.infinite),
    )));
  }
  @override
  void dispose(){motor.dispose();watch.stop();super.dispose();}
}
class _FactoryPainter extends CustomPainter {
  _FactoryPainter(this.clock,this.age);
  final double clock,age;
  double ease(double x){x=x.clamp(0.0,1.0);return x*x*(3-2*x);}
  @override
  void paint(Canvas c,Size size) {
    c.save();c.scale(size.width/400,size.height/230);
    final p=Paint()..strokeCap=StrokeCap.round;
    c.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(0,0,400,230),const Radius.circular(12)),p..shader=const LinearGradient(begin:Alignment.topCenter,end:Alignment.bottomCenter,colors:[Color(0xFF102545),Color(0xFF071A2F)]).createShader(const Rect.fromLTWH(0,0,400,230)));
    p.shader=null;
    void line(Offset a,Offset b,Color col,double w){c.drawLine(a,b,p..color=col..strokeWidth=w..style=PaintingStyle.stroke);p.style=PaintingStyle.fill;}
    void box(Rect r,List<Color> colors,double radius) {
      c.drawRRect(RRect.fromRectAndRadius(r,Radius.circular(radius)),p..shader=LinearGradient(begin:Alignment.topLeft,end:Alignment.bottomRight,colors:colors).createShader(r));p.shader=null;
    }
    void poly(List<Offset> points,Color color) {
      final path=Path()..addPolygon(points,true);c.drawPath(path,p..color=color);
    }
    void gear(double x,double y,int teeth,double direction) {
      c.save();c.translate(x,y);c.rotate(clock*direction);
      for(var i=0;i<teeth;i++){
        c.save();c.rotate(i*math.pi*2/teeth);c.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(-3,-24,6,13),const Radius.circular(2)),p..color=const Color(0xFF6886AA));c.restore();
      }
      c.drawCircle(Offset.zero,16,p..color=const Color(0xFF49617F));c.drawCircle(Offset.zero,8,p..color=const Color(0xFF8DE7FB));c.restore();
    }
    for(final side in [-1,1]) {
      final x=200+side*150.0;
      box(Rect.fromLTWH(x-16,25,32,154),[const Color(0xFF607FA5),const Color(0xFF1F385B)],6);
      for(var i=0;i<4;i++)line(Offset(x-11,53+i*25.0),Offset(x+11,53+i*25.0),const Color(0xFF63D5ED),3);
      gear(x,38,9,side*.6);
      final reach=14*ease(age/.5);
      line(Offset(x,102),Offset(x-side*(40+reach),81),const Color(0xFFE9B657),13);
      line(Offset(x-side*(40+reach),81),Offset(x-side*65,114),const Color(0xFF8AA9C6),9);
    }
    c.drawOval(const Rect.fromLTWH(72,172,256,45),p..color=const Color(0xFF172F4B));
    c.drawOval(const Rect.fromLTWH(82,169,236,34),p..color=const Color(0xFF52DBF4)..style=PaintingStyle.stroke..strokeWidth=4);p.style=PaintingStyle.fill;
    c.drawOval(const Rect.fromLTWH(87,174,226,23),p..color=const Color(0xFF263F62));
    final opening=age>=0;
    final anticipation=opening?math.sin(age*32)*math.max(0,1-age/1.2)*3:math.sin(clock*2)*1.5;
    c.save();c.translate(anticipation,0);
    final unlock=opening?ease((age-.5)/.6):0.0;
    final rise=opening?ease((age-1.05)/.85):0.0;
    box(const Rect.fromLTWH(136,104,128,77),[const Color(0xFF9ABAD9),const Color(0xFF355579)],9);
    poly([const Offset(264,104),const Offset(282,91),const Offset(282,167),const Offset(264,181)],const Color(0xFF294262));
    box(const Rect.fromLTWH(145,116,110,53),[const Color(0xFF335687),const Color(0xFF182C50)],5);
    for(final side in [-1,1])box(Rect.fromLTWH(194+side*(36+unlock*18),116,12,50),[const Color(0xFFF8D477),const Color(0xFF9C6D2D)],3);
    box(Rect.fromLTWH(185-unlock*40,128,30,24),[const Color(0xFFD7F9FF),const Color(0xFF5688AB)],4);
    c.drawCircle(Offset(200-unlock*40,140),5,p..color=const Color(0xFF6DF5FF));
    c.save();c.translate(0,-rise*68);
    poly([const Offset(136,104),const Offset(158,87),const Offset(282,87),const Offset(264,104)],const Color(0xFFB6D3ED));
    box(const Rect.fromLTWH(136,94,129,16),[const Color(0xFF8BDFF4),const Color(0xFF3B698C)],4);
    c.restore();c.restore();
    if(opening && rise>0){
      final origin=Offset(200,119-rise*33);
      c.drawCircle(origin,70+rise*12,p..shader=RadialGradient(colors:[Color.fromRGBO(136,220,255,.6*rise),const Color(0x0046BFFF)]).createShader(Rect.fromCircle(center:origin,radius:83)));p.shader=null;
      for(var i=0;i<24;i++) {
        final t=(age-1.1-i*.018).clamp(0.0,2.2);final a=i*2.399;
        final pos=origin+Offset(math.cos(a)*t*39,math.sin(a)*t*34-t*25);
        c.drawCircle(pos,2.2,p..color=Color.fromRGBO(168,238,255,(1-t/2.2).clamp(0.0,1.0)));
      }
      if(age>1.6){
        final text=TextPainter(text:const TextSpan(text:'НАГРАДЫ ПОЛУЧЕНЫ',style:TextStyle(color:Color(0xFFE4F8FF),fontSize:13,fontWeight:FontWeight.w800)),textDirection:TextDirection.ltr)..layout(maxWidth:240);
        text.paint(c,Offset(200-text.width/2,208));
      }
    }
    c.restore();
  }
  @override
  bool shouldRepaint(covariant _FactoryPainter old)=>old.clock!=clock || old.age!=age;
}
