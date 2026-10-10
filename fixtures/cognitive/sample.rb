# Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
class Sample
  def chain(a)
    if a == 1
      1
    elsif a == 2
      2
    else
      3
    end
  end

  def guards(a, b)
    return 0 unless a
    return 1 if a && b and a > 1
    a ? 2 : 3
  end

  def loops(xs)
    xs.each do |x|
      while x > 0
        x -= 1
        next if x.odd?
      end
    end
    i = 0
    i += 1 until i > 3
    for y in xs
      puts y
    end
  end

  def kind(v)
    case v
    when Integer then v.zero? ? :zero : :int
    else :other
    end
  end

  def shape(v)
    case v
    in [x, y] then x || y
    in {r:} then r
    end
  rescue NoMatchingPatternError
    self.shape([0, 0])
  end

  def self.build(n)
    make = ->(k) { k > 0 ? k : 0 }
    n.zero? ? make.(1) : build(n - 1)
  end
end
